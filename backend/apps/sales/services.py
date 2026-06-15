"""Sale write-paths: create a receipt, decrement product stock, snapshot costs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementReason

from .models import PaymentMethod, Sale, SaleChannel, SaleItem

if TYPE_CHECKING:
    from apps.accounts.models import User


def generate_receipt_number(when: datetime | None = None) -> str:
    when = when or timezone.now()
    return f"R{when:%Y%m%d}-{uuid4().hex[:6].upper()}"


@transaction.atomic
def create_sale(
    *,
    items: Sequence[dict],
    payment_method: str = PaymentMethod.CASH,
    channel: str = SaleChannel.COUNTER,
    discount: Decimal = Decimal("0"),
    customer_name: str = "",
    customer_phone: str = "",
    notes: str = "",
    occurred_at: datetime | None = None,
    user: "User | None" = None,
    wallet=None,
    allow_negative_stock: bool = False,
) -> Sale:
    """Create a Sale with its items, atomically decrementing stock for each product.

    Each entry in `items` is a dict: {"product": <Product>, "quantity": Decimal,
    optional "unit_price": Decimal}.
    """
    if not items:
        raise ValueError("Sale must contain at least one item.")

    occurred_at = occurred_at or timezone.now()

    sale = Sale.objects.create(
        receipt_number=generate_receipt_number(occurred_at),
        occurred_at=occurred_at,
        payment_method=payment_method,
        channel=channel,
        discount=Decimal(discount),
        customer_name=customer_name,
        customer_phone=customer_phone,
        notes=notes,
        served_by=user,
        wallet=wallet,
    )

    subtotal = Decimal("0")
    cost_of_goods = Decimal("0")

    for entry in items:
        product: Product = entry["product"]
        quantity = Decimal(entry["quantity"])
        unit_price = Decimal(entry.get("unit_price", product.selling_price))
        unit_cost = Decimal(product.production_cost or 0)
        line_total = (unit_price * quantity).quantize(Decimal("0.01"))

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            unit_cost=unit_cost,
            line_total=line_total,
        )

        subtotal += line_total
        cost_of_goods += (unit_cost * quantity).quantize(Decimal("0.01"))

        product_stock = inventory_services.ensure_stock_item(product=product)
        inventory_services.adjust_stock(
            stock_item=product_stock,
            quantity_delta=-quantity,
            reason=MovementReason.SALE,
            reference=sale.receipt_number,
            note=f"Sold on receipt {sale.receipt_number}",
            user=user,
            allow_negative=allow_negative_stock,
        )

    total = (subtotal - Decimal(discount)).quantize(Decimal("0.01"))
    if total < 0:
        total = Decimal("0")

    sale.subtotal = subtotal.quantize(Decimal("0.01"))
    sale.total = total
    sale.cost_of_goods = cost_of_goods.quantize(Decimal("0.01"))
    sale.save(update_fields=["subtotal", "total", "cost_of_goods", "updated_at"])

    return sale


@transaction.atomic
def update_sale(
    *,
    sale: Sale,
    items: Sequence[dict],
    payment_method: str = PaymentMethod.CASH,
    channel: str = SaleChannel.COUNTER,
    discount: Decimal = Decimal("0"),
    customer_name: str = "",
    customer_phone: str = "",
    notes: str = "",
    occurred_at: datetime | None = None,
    user: "User | None" = None,
    wallet=None,
    allow_negative_stock: bool = False,
) -> Sale:
    """Edit an existing Sale in place, keeping stock and totals consistent.

    The original line items are reversed back onto stock, then the new
    `items` are applied exactly like a fresh sale. The receipt number is
    preserved so any references to the sale stay stable.
    """
    if not items:
        raise ValueError("Sale must contain at least one item.")

    occurred_at = occurred_at or sale.occurred_at

    # Put the originally-sold quantities back before re-applying the new lines.
    for old_item in sale.items.select_related("product").all():
        product_stock = inventory_services.ensure_stock_item(product=old_item.product)
        inventory_services.adjust_stock(
            stock_item=product_stock,
            quantity_delta=old_item.quantity,
            reason=MovementReason.ADJUSTMENT_IN,
            reference=sale.receipt_number,
            note=f"Reversal — edit of receipt {sale.receipt_number}",
            user=user,
            allow_negative=True,
        )
    sale.items.all().delete()

    subtotal = Decimal("0")
    cost_of_goods = Decimal("0")

    for entry in items:
        product: Product = entry["product"]
        quantity = Decimal(entry["quantity"])
        unit_price = Decimal(entry.get("unit_price", product.selling_price))
        unit_cost = Decimal(product.production_cost or 0)
        line_total = (unit_price * quantity).quantize(Decimal("0.01"))

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            unit_cost=unit_cost,
            line_total=line_total,
        )

        subtotal += line_total
        cost_of_goods += (unit_cost * quantity).quantize(Decimal("0.01"))

        product_stock = inventory_services.ensure_stock_item(product=product)
        inventory_services.adjust_stock(
            stock_item=product_stock,
            quantity_delta=-quantity,
            reason=MovementReason.SALE,
            reference=sale.receipt_number,
            note=f"Sold on receipt {sale.receipt_number}",
            user=user,
            allow_negative=allow_negative_stock,
        )

    total = (subtotal - Decimal(discount)).quantize(Decimal("0.01"))
    if total < 0:
        total = Decimal("0")

    sale.occurred_at = occurred_at
    sale.payment_method = payment_method
    sale.channel = channel
    sale.discount = Decimal(discount)
    sale.customer_name = customer_name
    sale.customer_phone = customer_phone
    sale.notes = notes
    sale.wallet = wallet
    sale.subtotal = subtotal.quantize(Decimal("0.01"))
    sale.total = total
    sale.cost_of_goods = cost_of_goods.quantize(Decimal("0.01"))
    sale.save()

    return sale


@transaction.atomic
def delete_sale(*, sale: Sale, user: "User | None" = None) -> None:
    """Delete a Sale, restoring the sold quantities back onto stock.

    Mirrors the reversal loop in :func:`update_sale`: each line item's
    quantity is added back to the product's stock (referencing the receipt
    number) before the Sale — and its SaleItems via CASCADE — is removed.
    """
    receipt_number = sale.receipt_number
    for item in sale.items.select_related("product").all():
        product_stock = inventory_services.ensure_stock_item(product=item.product)
        inventory_services.adjust_stock(
            stock_item=product_stock,
            quantity_delta=item.quantity,
            reason=MovementReason.RETURN,
            reference=receipt_number,
            note=f"Reversal — deletion of receipt {receipt_number}",
            user=user,
            allow_negative=True,
        )

    sale.delete()
