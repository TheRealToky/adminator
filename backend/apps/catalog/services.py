"""Catalog domain helpers — kept thin; most logic lives in app-specific services."""
from __future__ import annotations

from decimal import Decimal

from .models import Product


def compute_ingredient_cost(product: Product) -> Decimal:
    """Sum of raw recipe items + processed-material usages for one product unit."""
    total = Decimal("0")
    for item in product.recipe_items.select_related("raw_material").all():
        total += Decimal(item.quantity) * Decimal(item.raw_material.unit_cost)
    for usage in product.processed_usages.select_related("processed_material").all():
        total += Decimal(usage.quantity) * Decimal(usage.processed_material.unit_cost)
    return total


def compute_product_unit_cost(product: Product) -> Decimal:
    """Cost to produce one unit: ingredient cost + variable overhead."""
    ingredients = compute_ingredient_cost(product)
    overhead_pct = Decimal(product.overhead_pct or 0)
    overhead = ingredients * overhead_pct / Decimal("100")
    return (ingredients + overhead).quantize(Decimal("0.01"))


def refresh_product_unit_cost(product: Product) -> None:
    """Recompute and persist a product's stored production_cost from its current recipe."""
    unit_cost = compute_product_unit_cost(product)
    Product.objects.filter(pk=product.pk).update(production_cost=unit_cost)
