"""Daily sales — receipts with line items and payments."""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    CARD = "card", "Card"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    CREDIT = "credit", "Credit / On Account"


class SaleChannel(models.TextChoices):
    COUNTER = "counter", "Counter / Walk-in"
    ONLINE = "online", "Online order"
    DELIVERY = "delivery", "Delivery"
    WHOLESALE = "wholesale", "Wholesale / B2B"


class Sale(BaseModel):
    """A single customer transaction (one receipt)."""

    receipt_number = models.CharField(max_length=32, unique=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    channel = models.CharField(
        max_length=16, choices=SaleChannel.choices, default=SaleChannel.COUNTER
    )
    payment_method = models.CharField(
        max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    customer_name = models.CharField(max_length=160, blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)
    subtotal = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    cost_of_goods = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Sum of production cost of sold items at the time of sale.",
    )
    notes = models.TextField(blank=True)
    served_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sales",
    )
    wallet = models.ForeignKey(
        "finance.Wallet", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sales",
        help_text="Wallet the takings landed in. Drives that wallet's balance.",
    )

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["-occurred_at"]),
            models.Index(fields=["payment_method", "-occurred_at"]),
            models.Index(fields=["channel", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"#{self.receipt_number} — {self.total}"

    @property
    def profit(self) -> Decimal:
        return self.total - self.cost_of_goods


class SaleItem(BaseModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="sale_items"
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        help_text="Snapshot of product.production_cost at the time of sale.",
    )
    line_total = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta:
        ordering = ["sale", "id"]

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"
