"""Smoke tests for sale creation."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.models import Product, ProductCategory, RawMaterial, RecipeItem
from apps.inventory import services as inv_services
from apps.sales import services as sale_services
from apps.sales.models import Sale


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


@pytest.mark.django_db
def test_update_sale_reverses_stock_and_recomputes_totals(coffee, admin_user):
    stock = inv_services.ensure_stock_item(product=coffee)
    inv_services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("20"),
        reason="adjustment_in", user=admin_user,
    )
    sale = sale_services.create_sale(
        items=[{"product": coffee, "quantity": Decimal("3")}],
        user=admin_user,
    )
    receipt = sale.receipt_number

    sale = sale_services.update_sale(
        sale=sale,
        items=[{"product": coffee, "quantity": Decimal("5")}],
        discount=Decimal("500"),
        user=admin_user,
    )

    # Receipt is preserved; totals recomputed from the new line.
    assert sale.receipt_number == receipt
    assert sale.subtotal == Decimal("7500.00")
    assert sale.total == Decimal("7000.00")
    assert sale.cost_of_goods == Decimal("1500.00")
    # Original 3 restored, new 5 taken: 20 - 3 + 3 - 5 = 15.
    stock.refresh_from_db()
    assert stock.quantity == Decimal("15.0000")


@pytest.mark.django_db
def test_delete_sale_restores_stock(coffee, admin_user):
    stock = inv_services.ensure_stock_item(product=coffee)
    inv_services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("20"),
        reason="adjustment_in", user=admin_user,
    )
    sale = sale_services.create_sale(
        items=[{"product": coffee, "quantity": Decimal("3")}],
        user=admin_user,
    )
    # Stock dropped to 17 at sale time.
    stock.refresh_from_db()
    assert stock.quantity == Decimal("17.0000")

    sale_id = sale.pk
    sale_services.delete_sale(sale=sale, user=admin_user)

    # Sale (and its items via CASCADE) is gone and the 3 units are back on the shelf.
    assert not Sale.objects.filter(pk=sale_id).exists()
    stock.refresh_from_db()
    assert stock.quantity == Decimal("20.0000")
