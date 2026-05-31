"""Smoke tests for the stock service layer."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.models import Product, ProductCategory, RawMaterial
from apps.finance.models import Expense, ExpenseCategory
from apps.inventory import services
from apps.inventory.models import MovementReason, StockMovement


@pytest.fixture
def flour(db) -> RawMaterial:
    return RawMaterial.objects.create(
        sku="RM-T-FL", name="Test flour", unit="g",
        unit_cost=Decimal("1"), reorder_threshold=Decimal("100"),
    )


@pytest.fixture
def croissant(db) -> Product:
    cat = ProductCategory.objects.create(name="Test pastries")
    return Product.objects.create(
        sku="PR-T-CR", name="Test croissant", category=cat,
        unit="unit", selling_price=Decimal("1200"),
        production_cost=Decimal("400"),
    )


@pytest.mark.django_db
def test_receive_raw_material_increments_stock(flour, admin_user):
    movement = services.receive_raw_material(
        raw_material=flour, quantity=Decimal("1000"), user=admin_user
    )
    assert movement.reason == MovementReason.PURCHASE
    assert movement.balance_after == Decimal("1000.0000")
    assert StockMovement.objects.filter(stock_item__raw_material=flour).count() == 1


@pytest.mark.django_db
def test_adjust_stock_below_zero_blocked(flour, admin_user):
    from apps.core.exceptions import InsufficientStock
    services.receive_raw_material(
        raw_material=flour, quantity=Decimal("50"), user=admin_user
    )
    stock = services.ensure_stock_item(raw_material=flour)
    with pytest.raises(InsufficientStock):
        services.adjust_stock(
            stock_item=stock,
            quantity_delta=Decimal("-100"),
            reason=MovementReason.ADJUSTMENT_OUT,
            user=admin_user,
        )


@pytest.mark.django_db
def test_record_waste_product_decrements_and_books_expense(croissant, admin_user):
    stock = services.ensure_stock_item(product=croissant)
    services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("30"),
        reason=MovementReason.ADJUSTMENT_IN, user=admin_user,
    )

    movement, expense = services.record_waste(
        product=croissant, quantity=Decimal("5"),
        note="spoiled overnight", user=admin_user,
    )

    stock.refresh_from_db()
    assert stock.quantity == Decimal("25.0000")
    assert movement.reason == MovementReason.WASTE
    assert movement.quantity_delta == Decimal("-5.0000")
    assert expense is not None
    assert expense.amount == Decimal("2000.00")  # 5 × 400
    assert expense.category.name == services.INVENTORY_WRITE_OFF_CATEGORY
    assert expense.recorded_by == admin_user


@pytest.mark.django_db
def test_record_waste_raw_material_uses_unit_cost(flour, admin_user):
    services.receive_raw_material(
        raw_material=flour, quantity=Decimal("500"), user=admin_user
    )

    movement, expense = services.record_waste(
        raw_material=flour, quantity=Decimal("120"), user=admin_user
    )

    assert movement.quantity_delta == Decimal("-120.0000")
    assert expense is not None
    assert expense.amount == Decimal("120.00")  # 120 × 1


@pytest.mark.django_db
def test_record_waste_reuses_write_off_category(croissant, admin_user):
    stock = services.ensure_stock_item(product=croissant)
    services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("10"),
        reason=MovementReason.ADJUSTMENT_IN, user=admin_user,
    )

    services.record_waste(product=croissant, quantity=Decimal("2"), user=admin_user)
    services.record_waste(product=croissant, quantity=Decimal("3"), user=admin_user)

    assert ExpenseCategory.objects.filter(
        name=services.INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 1
    assert Expense.objects.filter(
        category__name=services.INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 2


@pytest.mark.django_db
def test_record_waste_skips_expense_when_cost_is_zero(admin_user):
    cat = ProductCategory.objects.create(name="Freebies")
    freebie = Product.objects.create(
        sku="PR-T-FR", name="Free sample", category=cat,
        unit="unit", selling_price=Decimal("0"),
        production_cost=Decimal("0"),
    )
    stock = services.ensure_stock_item(product=freebie)
    services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("5"),
        reason=MovementReason.ADJUSTMENT_IN, user=admin_user,
    )

    movement, expense = services.record_waste(
        product=freebie, quantity=Decimal("2"), user=admin_user
    )

    assert movement.reason == MovementReason.WASTE
    assert expense is None


@pytest.mark.django_db
def test_record_waste_blocked_when_insufficient(flour, admin_user):
    from apps.core.exceptions import InsufficientStock
    services.receive_raw_material(
        raw_material=flour, quantity=Decimal("10"), user=admin_user
    )
    with pytest.raises(InsufficientStock):
        services.record_waste(
            raw_material=flour, quantity=Decimal("50"), user=admin_user
        )
    # And nothing was booked.
    assert Expense.objects.filter(
        category__name=services.INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 0


@pytest.mark.django_db
def test_record_waste_rejects_zero_quantity(flour, admin_user):
    services.receive_raw_material(
        raw_material=flour, quantity=Decimal("100"), user=admin_user
    )
    with pytest.raises(ValueError):
        services.record_waste(
            raw_material=flour, quantity=Decimal("0"), user=admin_user
        )
