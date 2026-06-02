"""Inventory: on-hand stock & full movement audit log."""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel


class ItemKind(models.TextChoices):
    PRODUCT = "product", "Finished product"
    RAW_MATERIAL = "raw_material", "Raw material"


class MovementReason(models.TextChoices):
    PURCHASE = "purchase", "Purchase (raw material received)"
    PRODUCTION_IN = "production_in", "Production output"
    PRODUCTION_OUT = "production_out", "Production consumption"
    SALE = "sale", "Sale"
    ADJUSTMENT_IN = "adjustment_in", "Manual adjustment (in)"
    ADJUSTMENT_OUT = "adjustment_out", "Manual adjustment (out)"
    WASTE = "waste", "Waste / loss"
    RETURN = "return", "Customer return"


class StockItem(BaseModel):
    """Current on-hand quantity for either a Product or a RawMaterial.

    Exactly one of `product` or `raw_material` is set — kept as nullable FKs
    with a constraint to keep queries simple and joins direct.
    """

    kind = models.CharField(max_length=20, choices=ItemKind.choices)
    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="stock",
        null=True,
        blank=True,
    )
    raw_material = models.OneToOneField(
        "catalog.RawMaterial",
        on_delete=models.CASCADE,
        related_name="stock",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="stock_item_one_target",
                condition=(
                    models.Q(kind="product", product__isnull=False, raw_material__isnull=True)
                    | models.Q(
                        kind="raw_material",
                        raw_material__isnull=False,
                        product__isnull=True,
                    )
                ),
            )
        ]
        indexes = [models.Index(fields=["kind"])]

    def __str__(self) -> str:
        target = self.product or self.raw_material
        return f"{target} · {self.quantity}"

    # ── Convenience accessors used by services / serializers ────────────
    @property
    def item_name(self) -> str:
        target = self.product or self.raw_material
        return target.name if target else "(unknown)"

    @property
    def item_sku(self) -> str:
        target = self.product or self.raw_material
        return target.sku if target else ""

    @property
    def item_unit(self) -> str:
        target = self.product or self.raw_material
        return target.unit if target else ""

    @property
    def reorder_threshold(self) -> Decimal:
        target = self.product or self.raw_material
        return Decimal(target.reorder_threshold) if target else Decimal("0")

    @property
    def item_unit_cost(self) -> Decimal:
        """Per-unit cost used for write-offs / valuation.

        Finished products use ``production_cost``; raw materials use
        ``unit_cost``. Both reflect the latest stored value (write-offs at the
        time of the loss are valued at the current cost on file).
        """
        if self.product_id and self.product is not None:
            return Decimal(self.product.production_cost or 0)
        if self.raw_material_id and self.raw_material is not None:
            return Decimal(self.raw_material.unit_cost or 0)
        return Decimal("0")

    @property
    def is_low(self) -> bool:
        return self.quantity <= self.reorder_threshold


class StockMovement(BaseModel):
    """Append-only ledger of every stock change."""

    stock_item = models.ForeignKey(
        StockItem, on_delete=models.PROTECT, related_name="movements"
    )
    reason = models.CharField(max_length=20, choices=MovementReason.choices)
    quantity_delta = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        help_text="Signed change. Positive = added; negative = removed.",
    )
    balance_after = models.DecimalField(max_digits=14, decimal_places=4)
    reference = models.CharField(
        max_length=160,
        blank=True,
        help_text="Free-text reference: invoice number, run id, etc.",
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stock_item", "-created_at"]),
            models.Index(fields=["reason", "-created_at"]),
        ]

    def __str__(self) -> str:
        sign = "+" if self.quantity_delta >= 0 else ""
        return f"{self.stock_item.item_name} {sign}{self.quantity_delta} ({self.get_reason_display()})"
