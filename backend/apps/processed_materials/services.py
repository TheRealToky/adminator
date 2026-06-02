"""Atomic operations for processed materials.

All stock changes flow through here. They (a) lock the row, (b) update the
balance, (c) record the movement. Batch production also consumes raw materials
via the existing inventory service.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.catalog import services as catalog_services
from apps.core.exceptions import InsufficientStock
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementReason

from .models import (
    ProcessedMaterial,
    ProcessedMaterialBatch,
    ProcessedMaterialMovementReason,
    ProcessedMaterialStock,
    ProcessedMaterialStockMovement,
)

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.catalog.models import Product


def ensure_stock(processed_material: ProcessedMaterial) -> ProcessedMaterialStock:
    stock, _ = ProcessedMaterialStock.objects.get_or_create(
        processed_material=processed_material,
        defaults={"quantity": Decimal("0")},
    )
    return stock


def compute_batch_cost(processed_material: ProcessedMaterial) -> Decimal:
    """Total ingredient cost for ONE standard batch.

    Ingredients can be either raw materials or other processed materials
    (sub-recipes); both contribute via their stored ``unit_cost``.
    """
    total = Decimal("0")
    items = processed_material.recipe_items.select_related(
        "raw_material", "sub_processed_material"
    ).all()
    for item in items:
        total += Decimal(item.quantity) * item.ingredient_unit_cost
    return total.quantize(Decimal("0.01"))


def compute_unit_cost(processed_material: ProcessedMaterial) -> Decimal:
    """Per-unit cost projected from the current recipe + variable overhead.

    Formula: ((batch_ingredient_cost × (1 + overhead_pct/100)) / yield_per_batch).
    """
    yield_per_batch = Decimal(processed_material.yield_per_batch)
    if yield_per_batch <= 0:
        return Decimal("0")
    batch_cost = compute_batch_cost(processed_material)
    overhead_pct = Decimal(processed_material.overhead_pct or 0)
    overhead = batch_cost * overhead_pct / Decimal("100")
    return ((batch_cost + overhead) / yield_per_batch).quantize(Decimal("0.0001"))


def refresh_unit_cost(
    processed_material: ProcessedMaterial,
    _visited: set | None = None,
) -> None:
    """Recompute stored unit_cost and cascade to dependents.

    Dependents include:
      - Parent processed materials whose recipes include this one as a
        sub-ingredient (recursive).
      - Products that use this processed material.

    ``_visited`` guards against cycles. Cycles shouldn't exist (the serializer
    blocks them), but if a legacy DB row sneaks one through we don't want to
    blow the stack.
    """
    if _visited is None:
        _visited = set()
    if processed_material.pk in _visited:
        return
    _visited.add(processed_material.pk)

    unit_cost = compute_unit_cost(processed_material)
    ProcessedMaterial.objects.filter(pk=processed_material.pk).update(unit_cost=unit_cost)

    for parent_item in processed_material.used_in_processed_materials.select_related(
        "processed_material"
    ).all():
        refresh_unit_cost(parent_item.processed_material, _visited=_visited)

    for usage in processed_material.used_in_products.select_related("product").all():
        catalog_services.refresh_product_unit_cost(usage.product)


@transaction.atomic
def adjust_stock(
    *,
    stock: ProcessedMaterialStock,
    quantity_delta: Decimal,
    reason: str,
    reference: str = "",
    note: str = "",
    user: "User | None" = None,
    allow_negative: bool = False,
) -> ProcessedMaterialStockMovement:
    locked = ProcessedMaterialStock.objects.select_for_update().get(pk=stock.pk)
    new_balance = locked.quantity + Decimal(quantity_delta)

    if new_balance < 0 and not allow_negative:
        raise InsufficientStock(
            detail=(
                f"Not enough {locked.item_name}: "
                f"have {locked.quantity}, need {-quantity_delta}."
            )
        )

    locked.quantity = new_balance
    locked.save(update_fields=["quantity", "updated_at"])

    return ProcessedMaterialStockMovement.objects.create(
        stock=locked,
        reason=reason,
        quantity_delta=quantity_delta,
        balance_after=new_balance,
        reference=reference,
        note=note,
        created_by=user,
    )


@transaction.atomic
def produce_batch(
    *,
    processed_material: ProcessedMaterial,
    batches: Decimal = Decimal("1"),
    scheduled_for=None,
    notes: str = "",
    user: "User | None" = None,
) -> ProcessedMaterialBatch:
    """Run the recipe: consume raw materials, increment processed-material stock."""
    batches = Decimal(batches)
    scheduled_for = scheduled_for or timezone.localdate()

    recipe_items = (
        processed_material.recipe_items
        .select_related("raw_material", "sub_processed_material")
        .all()
    )
    if not recipe_items:
        raise ValueError(
            f"Processed material '{processed_material.name}' has no recipe — "
            "cannot produce a batch."
        )

    quantity_produced = (
        batches * Decimal(processed_material.yield_per_batch)
    ).quantize(Decimal("0.0001"))

    batch_obj = ProcessedMaterialBatch.objects.create(
        processed_material=processed_material,
        batches=batches,
        quantity_produced=quantity_produced,
        scheduled_for=scheduled_for,
        notes=notes,
        created_by=user,
    )

    total_cost = Decimal("0")
    for item in recipe_items:
        needed = Decimal(item.quantity) * batches
        if item.sub_processed_material_id:
            sub_stock = ensure_stock(item.sub_processed_material)
            adjust_stock(
                stock=sub_stock,
                quantity_delta=-needed,
                reason=ProcessedMaterialMovementReason.PRODUCTION_OUT,
                reference=f"PMBATCH-{batch_obj.id}",
                note=f"Used in processed material batch {batch_obj.id}",
                user=user,
            )
            total_cost += needed * Decimal(item.sub_processed_material.unit_cost)
        else:
            material_stock = inventory_services.ensure_stock_item(
                raw_material=item.raw_material
            )
            inventory_services.adjust_stock(
                stock_item=material_stock,
                quantity_delta=-needed,
                reason=MovementReason.PRODUCTION_OUT,
                reference=f"PMBATCH-{batch_obj.id}",
                note=f"Used in processed material batch {batch_obj.id}",
                user=user,
            )
            total_cost += needed * Decimal(item.raw_material.unit_cost)

    # Increment processed material stock.
    stock = ensure_stock(processed_material)
    adjust_stock(
        stock=stock,
        quantity_delta=quantity_produced,
        reason=ProcessedMaterialMovementReason.BATCH_IN,
        reference=f"PMBATCH-{batch_obj.id}",
        note=f"Output of batch {batch_obj.id}",
        user=user,
    )

    batch_obj.cost = total_cost.quantize(Decimal("0.01"))
    batch_obj.completed_at = timezone.now()
    batch_obj.save(update_fields=["cost", "completed_at", "updated_at"])

    # Keep per-unit cost in sync with the recipe + overhead formula so it doesn't
    # silently lose the overhead estimate after a batch.
    refresh_unit_cost(processed_material)

    return batch_obj


@transaction.atomic
def record_waste(
    *,
    processed_material: ProcessedMaterial,
    quantity: Decimal,
    note: str = "",
    reference: str = "",
    user: "User | None" = None,
) -> tuple[ProcessedMaterialStockMovement, "object | None"]:
    """Write off processed-material stock as waste/loss AND book the cost.

    The expense is booked at ``processed_material.unit_cost × quantity`` — i.e.
    only the production cost of the wasted units flows into the P&L, mirroring
    how raw materials and finished products are written off.

    Returns ``(movement, expense)``. ``expense`` is ``None`` only when the
    per-unit cost is zero (nothing meaningful to charge).
    """
    # Local imports to avoid finance↔inventory↔processed-materials cycles
    # at module load.
    from apps.finance.models import Expense, ExpenseCategory
    from apps.inventory.services import INVENTORY_WRITE_OFF_CATEGORY

    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValueError("Waste quantity must be positive.")

    unit_cost = Decimal(processed_material.unit_cost or 0)
    stock = ensure_stock(processed_material)

    movement = adjust_stock(
        stock=stock,
        quantity_delta=-quantity,
        reason=ProcessedMaterialMovementReason.WASTE,
        reference=reference,
        note=note,
        user=user,
    )

    write_off_amount = (unit_cost * quantity).quantize(Decimal("0.01"))
    expense = None
    if write_off_amount > 0:
        category, _ = ExpenseCategory.objects.get_or_create(
            name=INVENTORY_WRITE_OFF_CATEGORY,
            defaults={
                "description": "Stock written off as waste, spoilage, expiry or loss.",
            },
        )
        expense = Expense.objects.create(
            category=category,
            title=f"Write-off: {processed_material.name}",
            amount=write_off_amount,
            reference=reference or f"WASTE-PM-{movement.id}",
            notes=note,
            recorded_by=user,
        )

    return movement, expense


@transaction.atomic
def consume_for_product_run(
    *,
    product: "Product",
    product_quantity: Decimal,
    reference: str,
    user: "User | None" = None,
    allow_negative: bool = False,
) -> None:
    """Decrement processed materials used by a product production run.

    Called from a post-save signal when a ProductionRun is completed.
    """
    usages = product.processed_usages.select_related("processed_material").all()
    for usage in usages:
        needed = Decimal(usage.quantity) * Decimal(product_quantity)
        stock = ensure_stock(usage.processed_material)
        adjust_stock(
            stock=stock,
            quantity_delta=-needed,
            reason=ProcessedMaterialMovementReason.PRODUCTION_OUT,
            reference=reference,
            note=f"Used by product run {reference}",
            user=user,
            allow_negative=allow_negative,
        )
