"""Processed materials — middlemen between raw materials and finished products.

Examples: pizza dough, crepe batter, choux pastry, ganache, frangipane.

These are produced in batches from raw materials, kept in stock, then drawn down
when finished products that include them are made.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.catalog.models import UnitOfMeasure
from apps.core.models import BaseModel


class ProcessedMaterial(BaseModel):
    """A semi-finished good prepared in batches."""

    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    unit = models.CharField(max_length=10, choices=UnitOfMeasure.choices)
    yield_per_batch = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Units produced by one standard batch.",
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Derived: (batch cost + overhead) / yield_per_batch.",
    )
    overhead_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Variable overhead estimate as a percentage of ingredient cost.",
    )
    shelf_life_hours = models.PositiveIntegerField(
        default=24,
        help_text="Hours the processed material remains usable after preparation.",
    )
    reorder_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Alert when on-hand falls to or below this.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class ProcessedMaterialRecipeItem(BaseModel):
    """One ingredient line in a processed material's batch recipe.

    An ingredient is either a raw material OR another processed material
    (sub-recipe). Exactly one of the two FKs is set per row; the CheckConstraint
    below enforces that and also blocks direct self-reference. Deeper cycles are
    blocked in the serializer layer.
    """

    processed_material = models.ForeignKey(
        ProcessedMaterial,
        on_delete=models.CASCADE,
        related_name="recipe_items",
    )
    raw_material = models.ForeignKey(
        "catalog.RawMaterial",
        on_delete=models.PROTECT,
        related_name="used_in_processed",
        null=True,
        blank=True,
    )
    sub_processed_material = models.ForeignKey(
        ProcessedMaterial,
        on_delete=models.PROTECT,
        related_name="used_in_processed_materials",
        null=True,
        blank=True,
        help_text="Another processed material used as an ingredient in this recipe.",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Quantity of the ingredient needed for ONE batch.",
    )

    class Meta:
        ordering = ["processed_material", "raw_material", "sub_processed_material"]
        constraints = [
            models.UniqueConstraint(
                fields=["processed_material", "raw_material"],
                condition=Q(raw_material__isnull=False),
                name="unique_pm_raw_material",
            ),
            models.UniqueConstraint(
                fields=["processed_material", "sub_processed_material"],
                condition=Q(sub_processed_material__isnull=False),
                name="unique_pm_sub_processed_material",
            ),
            models.CheckConstraint(
                check=(
                    (Q(raw_material__isnull=False) & Q(sub_processed_material__isnull=True))
                    | (Q(raw_material__isnull=True) & Q(sub_processed_material__isnull=False))
                ),
                name="pm_recipe_item_exactly_one_ingredient",
            ),
            models.CheckConstraint(
                check=~Q(sub_processed_material=F("processed_material")),
                name="pm_recipe_item_no_self_reference",
            ),
        ]

    def __str__(self) -> str:
        if self.sub_processed_material_id:
            child = self.sub_processed_material
            return (
                f"{self.processed_material.name} ← "
                f"{self.quantity} {child.unit} {child.name} (processed)"
            )
        return (
            f"{self.processed_material.name} ← "
            f"{self.quantity} {self.raw_material.unit} {self.raw_material.name}"
        )

    @property
    def ingredient_unit(self) -> str:
        if self.sub_processed_material_id:
            return self.sub_processed_material.unit
        return self.raw_material.unit

    @property
    def ingredient_unit_cost(self) -> Decimal:
        if self.sub_processed_material_id:
            return Decimal(self.sub_processed_material.unit_cost)
        return Decimal(self.raw_material.unit_cost)


class ProductProcessedMaterialUsage(BaseModel):
    """Bill-of-materials line: how much processed material goes into one product unit."""

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="processed_usages",
    )
    processed_material = models.ForeignKey(
        ProcessedMaterial,
        on_delete=models.PROTECT,
        related_name="used_in_products",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Amount of processed material per ONE product unit.",
    )

    class Meta:
        ordering = ["product", "processed_material"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "processed_material"],
                name="unique_product_pm",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.product.name} ← "
            f"{self.quantity} {self.processed_material.unit} {self.processed_material.name}"
        )


class ProcessedMaterialStock(BaseModel):
    """Current on-hand quantity of a processed material."""

    processed_material = models.OneToOneField(
        ProcessedMaterial,
        on_delete=models.CASCADE,
        related_name="stock",
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("0")
    )

    class Meta:
        ordering = ["processed_material__name"]

    def __str__(self) -> str:
        return f"{self.processed_material.name}: {self.quantity}"

    @property
    def item_name(self) -> str:
        return self.processed_material.name

    @property
    def item_sku(self) -> str:
        return self.processed_material.sku

    @property
    def item_unit(self) -> str:
        return self.processed_material.unit

    @property
    def reorder_threshold(self) -> Decimal:
        return Decimal(self.processed_material.reorder_threshold)

    @property
    def is_low(self) -> bool:
        return self.quantity <= self.reorder_threshold


class ProcessedMaterialMovementReason(models.TextChoices):
    BATCH_IN = "batch_in", "Batch produced"
    PRODUCTION_OUT = "production_out", "Used in product"
    ADJUSTMENT_IN = "adjustment_in", "Manual adjustment (in)"
    ADJUSTMENT_OUT = "adjustment_out", "Manual adjustment (out)"
    WASTE = "waste", "Waste / expired"


class ProcessedMaterialStockMovement(BaseModel):
    """Append-only ledger of every processed-material stock change."""

    stock = models.ForeignKey(
        ProcessedMaterialStock,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    reason = models.CharField(
        max_length=20, choices=ProcessedMaterialMovementReason.choices
    )
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=4)
    balance_after = models.DecimalField(max_digits=14, decimal_places=4)
    reference = models.CharField(max_length=160, blank=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_material_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stock", "-created_at"], name="pm_mov_stock_created_idx"),
            models.Index(fields=["reason", "-created_at"], name="pm_mov_reason_created_idx"),
        ]

    def __str__(self) -> str:
        sign = "+" if self.quantity_delta >= 0 else ""
        return (
            f"{self.stock.item_name} {sign}{self.quantity_delta} "
            f"({self.get_reason_display()})"
        )


class ProcessedMaterialBatch(BaseModel):
    """A batch production run that creates processed material from raw materials."""

    processed_material = models.ForeignKey(
        ProcessedMaterial,
        on_delete=models.PROTECT,
        related_name="batches",
    )
    batches = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="How many standard batches to run (each yields yield_per_batch).",
    )
    quantity_produced = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        help_text="Total units produced = batches × yield_per_batch.",
    )
    cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0")
    )
    scheduled_for = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_material_batches",
    )

    class Meta:
        ordering = ["-scheduled_for", "-created_at"]
        indexes = [
            models.Index(fields=["-scheduled_for"], name="pm_batch_sched_idx"),
            models.Index(
                fields=["processed_material", "-scheduled_for"],
                name="pm_batch_material_sched_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.processed_material.name} × {self.batches} batches"
