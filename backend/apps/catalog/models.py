"""Catalog: what we make (products), what goes in (raw materials), and who supplies."""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class UnitOfMeasure(models.TextChoices):
    # Mass
    GRAM = "g", "Gram (g)"
    KILOGRAM = "kg", "Kilogram (kg)"
    # Volume
    MILLILITER = "ml", "Milliliter (ml)"
    LITER = "l", "Liter (l)"
    # Discrete
    UNIT = "unit", "Unit"
    DOZEN = "dozen", "Dozen"
    PACK = "pack", "Pack"


class ProductCategory(BaseModel):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "product categories"

    def __str__(self) -> str:
        return self.name


class Supplier(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    contact_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(BaseModel):
    """A finished good sold to customers (e.g. croissant, baguette)."""

    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, related_name="products"
    )
    description = models.TextField(blank=True)
    unit = models.CharField(
        max_length=10, choices=UnitOfMeasure.choices, default=UnitOfMeasure.UNIT
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    production_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Derived/estimated cost to produce one unit.",
    )
    overhead_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Variable overhead estimate as a percentage of ingredient cost.",
    )
    reorder_threshold = models.PositiveIntegerField(
        default=10, help_text="Trigger a low-stock alert when on-hand falls to or below this."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"

    @property
    def margin(self) -> Decimal:
        return self.selling_price - self.production_cost


class RawMaterial(BaseModel):
    """An input consumed by production (flour, sugar, eggs, etc.)."""

    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    unit = models.CharField(max_length=10, choices=UnitOfMeasure.choices)
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Cost per single unit (e.g. per gram, per ml, per egg).",
    )
    reorder_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        help_text="Alert when on-hand quantity falls to or below this.",
    )
    preferred_supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raw_materials",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class RecipeItem(BaseModel):
    """Bill-of-materials line: how much raw material goes into one product."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="recipe_items"
    )
    raw_material = models.ForeignKey(
        RawMaterial, on_delete=models.PROTECT, related_name="used_in"
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Quantity of the raw material needed for ONE unit of the product.",
    )

    class Meta:
        ordering = ["product", "raw_material"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "raw_material"], name="unique_product_raw_material"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.name} ← {self.quantity} {self.raw_material.unit} {self.raw_material.name}"
