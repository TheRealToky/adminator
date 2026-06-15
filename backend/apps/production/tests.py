"""Tests for executing production runs.

Focus: a product whose recipe is made of processed materials (no raw recipe
items) must still produce — previously this raised a ValueError ("has no
recipe") and surfaced as a 500.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.models import Product, ProductCategory, RawMaterial, RecipeItem
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementReason
from apps.processed_materials import services as pm_services
from apps.processed_materials.models import (
    ProcessedMaterial,
    ProcessedMaterialMovementReason,
    ProductProcessedMaterialUsage,
)
from apps.production import services as production_services


@pytest.fixture
def category(db) -> ProductCategory:
    return ProductCategory.objects.create(name="Test pastries")


@pytest.fixture
def ganache(db) -> ProcessedMaterial:
    return ProcessedMaterial.objects.create(
        sku="PM-T-GAN", name="Test ganache", unit="g",
        yield_per_batch=Decimal("1000"),
        unit_cost=Decimal("2.5000"),
    )


@pytest.mark.django_db
def test_execute_production_with_processed_only_recipe(category, ganache, admin_user):
    """A processed-only recipe produces, consumes the processed material, and
    records the run cost from the processed-material unit cost."""
    product = Product.objects.create(
        sku="P-T-TRUFFLE", name="Truffle", category=category,
        selling_price=Decimal("10.00"),
    )
    ProductProcessedMaterialUsage.objects.create(
        product=product, processed_material=ganache, quantity=Decimal("8"),
    )
    # Park enough processed stock on the shelf so consumption is observable.
    pm_stock = pm_services.ensure_stock(ganache)
    pm_services.adjust_stock(
        stock=pm_stock,
        quantity_delta=Decimal("1000"),
        reason=ProcessedMaterialMovementReason.ADJUSTMENT_IN,
        user=admin_user,
    )

    run = production_services.execute_production(
        product=product, quantity=Decimal("10"), user=admin_user,
    )

    # 10 units × 8 g each = 80 g consumed.
    pm_stock.refresh_from_db()
    assert pm_stock.quantity == Decimal("920.0000")
    # Cost = 80 g × 2.50 = 200.00.
    assert run.cost == Decimal("200.00")


@pytest.mark.django_db
def test_execute_production_with_mixed_recipe(category, ganache, admin_user):
    """Raw + processed recipe: both costs roll into the run cost."""
    flour = RawMaterial.objects.create(
        sku="RM-T-FLOUR", name="Flour", unit="g", unit_cost=Decimal("0.0100"),
    )
    product = Product.objects.create(
        sku="P-T-CAKE", name="Cake", category=category,
        selling_price=Decimal("20.00"),
    )
    RecipeItem.objects.create(product=product, raw_material=flour, quantity=Decimal("100"))
    ProductProcessedMaterialUsage.objects.create(
        product=product, processed_material=ganache, quantity=Decimal("5"),
    )
    # Stock the flour so the raw-material draw-down has something to consume.
    flour_stock = inventory_services.ensure_stock_item(raw_material=flour)
    inventory_services.adjust_stock(
        stock_item=flour_stock,
        quantity_delta=Decimal("1000"),
        reason=MovementReason.PURCHASE,
        user=admin_user,
    )
    pm_stock = pm_services.ensure_stock(ganache)
    pm_services.adjust_stock(
        stock=pm_stock,
        quantity_delta=Decimal("1000"),
        reason=ProcessedMaterialMovementReason.ADJUSTMENT_IN,
        user=admin_user,
    )

    run = production_services.execute_production(
        product=product, quantity=Decimal("4"), user=admin_user,
    )

    # Raw: 4 × 100 g × 0.01 = 4.00; Processed: 4 × 5 g × 2.50 = 50.00 → 54.00.
    assert run.cost == Decimal("54.00")
    # Started at 1000 g, consumed 4 × 100 = 400 g.
    flour_stock.refresh_from_db()
    assert flour_stock.quantity == Decimal("600.0000")


@pytest.mark.django_db
def test_execute_production_with_no_recipe_raises(category, admin_user):
    product = Product.objects.create(
        sku="P-T-EMPTY", name="Empty", category=category,
        selling_price=Decimal("5.00"),
    )
    with pytest.raises(ValueError):
        production_services.execute_production(
            product=product, quantity=Decimal("1"), user=admin_user,
        )


@pytest.mark.django_db
def test_update_run_amends_metadata_only(category, ganache, admin_user, auth_client):
    """PATCHing a run edits the schedule date and notes; product, quantity and
    cost are locked so already-posted stock movements stay consistent."""
    product = Product.objects.create(
        sku="P-T-EDIT", name="Editable", category=category,
        selling_price=Decimal("12.00"),
    )
    ProductProcessedMaterialUsage.objects.create(
        product=product, processed_material=ganache, quantity=Decimal("4"),
    )
    pm_stock = pm_services.ensure_stock(ganache)
    pm_services.adjust_stock(
        stock=pm_stock,
        quantity_delta=Decimal("1000"),
        reason=ProcessedMaterialMovementReason.ADJUSTMENT_IN,
        user=admin_user,
    )
    run = production_services.execute_production(
        product=product, quantity=Decimal("3"), user=admin_user,
    )
    original_cost = run.cost

    resp = auth_client.patch(
        f"/api/v1/production/runs/{run.id}/",
        {
            "scheduled_for": "2030-01-15",
            "notes": "Pushed to mid-January",
            # These should be ignored — not declared on the update serializer.
            "quantity": "999",
            "product": str(category.id),
            "cost": "0.01",
        },
        format="json",
    )

    assert resp.status_code == 200
    run.refresh_from_db()
    assert str(run.scheduled_for) == "2030-01-15"
    assert run.notes == "Pushed to mid-January"
    # Locked fields untouched.
    assert run.quantity == Decimal("3.00")
    assert run.product == product
    assert run.cost == original_cost
