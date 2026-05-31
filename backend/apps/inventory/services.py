"""Inventory write-paths.

All stock changes flow through these helpers. They (a) take a row lock on the
StockItem to keep the math correct under concurrency, (b) update the running
balance, and (c) write the movement entry — atomically.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from apps.core.exceptions import InsufficientStock

from .models import ItemKind, MovementReason, StockItem, StockMovement

#: Auto-managed expense category booking inventory write-offs against P&L.
INVENTORY_WRITE_OFF_CATEGORY = "Inventory write-off"

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.catalog.models import Product, RawMaterial
    from apps.finance.models import Expense


def ensure_stock_item(*, product: "Product | None" = None,
                      raw_material: "RawMaterial | None" = None) -> StockItem:
    """Get or create the StockItem row for a product/raw material."""
    if (product is None) == (raw_material is None):
        raise ValueError("Pass exactly one of `product` or `raw_material`.")

    if product is not None:
        stock, _ = StockItem.objects.get_or_create(
            product=product,
            defaults={"kind": ItemKind.PRODUCT, "quantity": Decimal("0")},
        )
    else:
        stock, _ = StockItem.objects.get_or_create(
            raw_material=raw_material,
            defaults={"kind": ItemKind.RAW_MATERIAL, "quantity": Decimal("0")},
        )
    return stock


@transaction.atomic
def adjust_stock(
    *,
    stock_item: StockItem,
    quantity_delta: Decimal,
    reason: str,
    reference: str = "",
    note: str = "",
    user: "User | None" = None,
    allow_negative: bool = False,
) -> StockMovement:
    """Apply a signed quantity_delta to stock_item and record the movement."""

    locked = StockItem.objects.select_for_update().get(pk=stock_item.pk)
    new_balance = locked.quantity + Decimal(quantity_delta)

    if new_balance < 0 and not allow_negative:
        raise InsufficientStock(
            detail=(
                f"Not enough stock of {locked.item_name}: "
                f"have {locked.quantity}, requested {-quantity_delta}."
            )
        )

    locked.quantity = new_balance
    locked.save(update_fields=["quantity", "updated_at"])

    return StockMovement.objects.create(
        stock_item=locked,
        reason=reason,
        quantity_delta=quantity_delta,
        balance_after=new_balance,
        reference=reference,
        note=note,
        created_by=user,
    )


def receive_raw_material(
    *,
    raw_material: "RawMaterial",
    quantity: Decimal,
    reference: str = "",
    note: str = "",
    user: "User | None" = None,
) -> StockMovement:
    if quantity <= 0:
        raise ValueError("Quantity received must be positive.")
    stock = ensure_stock_item(raw_material=raw_material)
    return adjust_stock(
        stock_item=stock,
        quantity_delta=Decimal(quantity),
        reason=MovementReason.PURCHASE,
        reference=reference,
        note=note,
        user=user,
    )


@transaction.atomic
def record_waste(
    *,
    product: "Product | None" = None,
    raw_material: "RawMaterial | None" = None,
    quantity: Decimal,
    note: str = "",
    reference: str = "",
    user: "User | None" = None,
) -> tuple[StockMovement, "Expense | None"]:
    """Write off stock as waste/loss AND book the cost as a P&L expense.

    Returns (movement, expense). `expense` is None only when the item's
    per-unit cost is zero (nothing meaningful to charge).
    """
    # Local import to avoid a finance→inventory→finance cycle at module load.
    from apps.finance.models import Expense, ExpenseCategory

    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValueError("Waste quantity must be positive.")
    if (product is None) == (raw_material is None):
        raise ValueError("Pass exactly one of `product` or `raw_material`.")

    if product is not None:
        unit_cost = Decimal(product.production_cost or 0)
        item_name = product.name
        stock = ensure_stock_item(product=product)
    else:
        unit_cost = Decimal(raw_material.unit_cost or 0)
        item_name = raw_material.name
        stock = ensure_stock_item(raw_material=raw_material)

    movement = adjust_stock(
        stock_item=stock,
        quantity_delta=-quantity,
        reason=MovementReason.WASTE,
        reference=reference,
        note=note,
        user=user,
    )

    write_off_amount = (unit_cost * quantity).quantize(Decimal("0.01"))
    expense: "Expense | None" = None
    if write_off_amount > 0:
        category, _ = ExpenseCategory.objects.get_or_create(
            name=INVENTORY_WRITE_OFF_CATEGORY,
            defaults={
                "description": "Stock written off as waste, spoilage, expiry or loss.",
            },
        )
        expense = Expense.objects.create(
            category=category,
            title=f"Write-off: {item_name}",
            amount=write_off_amount,
            reference=reference or f"WASTE-{movement.id}",
            notes=note,
            recorded_by=user,
        )

    return movement, expense
