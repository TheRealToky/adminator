"""Tests for dashboard aggregations."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.analytics import services as analytics_services
from apps.catalog.models import Product, ProductCategory, RawMaterial
from apps.inventory import services as inv_services
from apps.inventory.models import MovementReason


@pytest.mark.django_db
def test_inventory_on_hand_value_sums_finished_and_raw(admin_user):
    cat = ProductCategory.objects.create(name="Breads")
    bread = Product.objects.create(
        sku="PR-T-BR", name="Test bread", category=cat,
        unit="unit", selling_price=Decimal("1200"),
        production_cost=Decimal("450"),
    )
    flour = RawMaterial.objects.create(
        sku="RM-T-FL", name="Test flour", unit="g",
        unit_cost=Decimal("2"), reorder_threshold=Decimal("100"),
    )

    bread_stock = inv_services.ensure_stock_item(product=bread)
    inv_services.adjust_stock(
        stock_item=bread_stock, quantity_delta=Decimal("20"),
        reason=MovementReason.ADJUSTMENT_IN, user=admin_user,
    )
    inv_services.receive_raw_material(
        raw_material=flour, quantity=Decimal("500"), user=admin_user
    )

    result = analytics_services.inventory_on_hand_value()

    assert result["finished_goods_value"] == Decimal("9000.00")   # 20 × 450
    assert result["finished_goods_units"] == Decimal("20.0000")
    assert result["raw_materials_value"] == Decimal("1000.00")    # 500 × 2
    assert result["total_value"] == Decimal("10000.00")


@pytest.mark.django_db
def test_inventory_on_hand_value_excludes_written_off_stock(admin_user):
    cat = ProductCategory.objects.create(name="Pastries")
    croissant = Product.objects.create(
        sku="PR-T-CR", name="Test croissant", category=cat,
        unit="unit", selling_price=Decimal("900"),
        production_cost=Decimal("300"),
    )
    stock = inv_services.ensure_stock_item(product=croissant)
    inv_services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("10"),
        reason=MovementReason.ADJUSTMENT_IN, user=admin_user,
    )
    inv_services.record_waste(
        product=croissant, quantity=Decimal("4"), user=admin_user
    )

    result = analytics_services.inventory_on_hand_value()

    # 6 units left × 300
    assert result["finished_goods_value"] == Decimal("1800.00")


@pytest.mark.django_db
def test_inventory_on_hand_value_empty():
    result = analytics_services.inventory_on_hand_value()
    assert result["finished_goods_value"] == Decimal("0.00")
    assert result["raw_materials_value"] == Decimal("0.00")
    assert result["total_value"] == Decimal("0.00")
