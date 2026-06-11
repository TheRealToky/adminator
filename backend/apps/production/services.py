"""Atomic production execution: consume raw materials, produce finished product."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.catalog import services as catalog_services
from apps.catalog.models import Product
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementReason

from .models import ProductionRun, ProductionStatus

if TYPE_CHECKING:
    from apps.accounts.models import User


def compute_unit_cost(product: Product) -> Decimal:
    """Sum of (recipe.quantity × material.unit_cost) for one product unit."""
    total = Decimal("0")
    for item in product.recipe_items.select_related("raw_material").all():
        total += Decimal(item.quantity) * Decimal(item.raw_material.unit_cost)
    return total.quantize(Decimal("0.01"))


@transaction.atomic
def execute_production(
    *,
    product: Product,
    quantity: Decimal,
    scheduled_for=None,
    notes: str = "",
    user: "User | None" = None,
    status: str = ProductionStatus.COMPLETED,
) -> ProductionRun:
    """Decrement raw materials per recipe; increment finished stock; record the run."""
    quantity = Decimal(quantity)
    scheduled_for = scheduled_for or timezone.localdate()

    run = ProductionRun.objects.create(
        product=product,
        quantity=quantity,
        scheduled_for=scheduled_for,
        notes=notes,
        created_by=user,
        status=status,
    )

    if status != ProductionStatus.COMPLETED:
        return run  # No stock movement until actually completed.

    # A product's recipe can be raw materials, processed materials, or a mix.
    # Processed-material stock is drawn down by a post-save signal in the
    # processed_materials app, but we still need their cost here — and must not
    # reject a processed-only recipe as if it had no recipe at all.
    recipe_items = product.recipe_items.select_related("raw_material").all()
    processed_usages = product.processed_usages.select_related("processed_material").all()
    if not recipe_items and not processed_usages:
        raise ValueError(
            f"Product '{product.name}' has no recipe — cannot execute production."
        )

    total_cost = Decimal("0")
    for item in recipe_items:
        needed = Decimal(item.quantity) * quantity
        material_stock = inventory_services.ensure_stock_item(raw_material=item.raw_material)
        inventory_services.adjust_stock(
            stock_item=material_stock,
            quantity_delta=-needed,
            reason=MovementReason.PRODUCTION_OUT,
            reference=f"PROD-{run.id}",
            note=f"Used in production run {run.id}",
            user=user,
        )
        total_cost += needed * Decimal(item.raw_material.unit_cost)

    # Processed materials: consumption happens in the signal; add their cost so
    # the run's recorded cost reflects the full bill of materials.
    for usage in processed_usages:
        total_cost += (
            Decimal(usage.quantity) * quantity * Decimal(usage.processed_material.unit_cost)
        )

    # Add finished product to stock.
    product_stock = inventory_services.ensure_stock_item(product=product)
    inventory_services.adjust_stock(
        stock_item=product_stock,
        quantity_delta=quantity,
        reason=MovementReason.PRODUCTION_IN,
        reference=f"PROD-{run.id}",
        note=f"Output of production run {run.id}",
        user=user,
    )

    run.cost = total_cost.quantize(Decimal("0.01"))
    run.completed_at = timezone.now()
    run.save(update_fields=["cost", "completed_at", "updated_at"])

    # Refresh product's per-unit cost from the current recipe + overhead, so it
    # stays consistent with the value shown in the recipe modal.
    catalog_services.refresh_product_unit_cost(product)

    return run
