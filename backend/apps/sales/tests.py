"""Smoke tests for sale creation."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.models import Product, ProductCategory, RawMaterial, RecipeItem
from apps.inventory import services as inv_services
from apps.sales import services as sale_services


@pytest.fixture
def coffee(db) -> Product:
    cat = ProductCategory.objects.create(name="Beverages")
    return Product.objects.create(
        sku="PR-T-CO", name="Test coffee", category=cat,
        unit="unit", selling_price=Decimal("1500"), production_cost=Decimal("300"),
    )


@pytest.mark.django_db
def test_sale_records_totals_and_decrements_stock(coffee, admin_user):
    stock = inv_services.ensure_stock_item(product=coffee)
    inv_services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("20"),
        reason="adjustment_in", user=admin_user,
    )
    sale = sale_services.create_sale(
        items=[{"product": coffee, "quantity": Decimal("3")}],
        user=admin_user,
    )
    assert sale.subtotal == Decimal("4500.00")
    assert sale.total == Decimal("4500.00")
    assert sale.cost_of_goods == Decimal("900.00")
    stock.refresh_from_db()
    assert stock.quantity == Decimal("17.0000")
