"""Smoke tests for processed-material write-offs.

The recipe / batch flow already has implicit coverage through analytics tests;
this module focuses on the write-off path because it is finance-touching
(it books an Expense) and shares the "Inventory write-off" category with the
inventory.services version.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.finance.models import Expense, ExpenseCategory
from apps.inventory.services import INVENTORY_WRITE_OFF_CATEGORY
from apps.processed_materials import services
from apps.processed_materials.models import (
    ProcessedMaterial,
    ProcessedMaterialMovementReason,
)


@pytest.fixture
def ganache(db) -> ProcessedMaterial:
    """A processed material with a non-zero per-unit cost."""
    return ProcessedMaterial.objects.create(
        sku="PM-T-GAN", name="Test ganache", unit="g",
        yield_per_batch=Decimal("1000"),
        unit_cost=Decimal("2.5000"),  # 2.50 / g
        reorder_threshold=Decimal("100"),
    )


def _seed_stock(material: ProcessedMaterial, qty: Decimal, user) -> None:
    """Park some stock on the shelf via the manual adjustment path."""
    stock = services.ensure_stock(material)
    services.adjust_stock(
        stock=stock,
        quantity_delta=qty,
        reason=ProcessedMaterialMovementReason.ADJUSTMENT_IN,
        user=user,
    )


@pytest.mark.django_db
def test_record_waste_decrements_and_books_expense(ganache, admin_user):
    _seed_stock(ganache, Decimal("400"), admin_user)

    movement, expense = services.record_waste(
        processed_material=ganache,
        quantity=Decimal("120"),
        note="spoiled — fridge died",
        user=admin_user,
    )

    stock = services.ensure_stock(ganache)
    assert stock.quantity == Decimal("280.0000")
    assert movement.reason == ProcessedMaterialMovementReason.WASTE
    assert movement.quantity_delta == Decimal("-120.0000")
    assert expense is not None
    assert expense.amount == Decimal("300.00")  # 120 × 2.5
    assert expense.category.name == INVENTORY_WRITE_OFF_CATEGORY
    assert expense.recorded_by == admin_user


@pytest.mark.django_db
def test_record_waste_reuses_shared_write_off_category(ganache, admin_user):
    _seed_stock(ganache, Decimal("500"), admin_user)

    services.record_waste(
        processed_material=ganache, quantity=Decimal("50"), user=admin_user,
    )
    services.record_waste(
        processed_material=ganache, quantity=Decimal("30"), user=admin_user,
    )

    # Same category as the inventory write-off — important so the P&L lumps
    # finished-goods, raw-material and processed-material write-offs together.
    assert ExpenseCategory.objects.filter(
        name=INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 1
    assert Expense.objects.filter(
        category__name=INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 2


@pytest.mark.django_db
def test_record_waste_skips_expense_when_cost_is_zero(admin_user):
    freebie = ProcessedMaterial.objects.create(
        sku="PM-T-FREE", name="Free sample paste", unit="g",
        yield_per_batch=Decimal("1000"),
        unit_cost=Decimal("0"),
    )
    _seed_stock(freebie, Decimal("100"), admin_user)

    movement, expense = services.record_waste(
        processed_material=freebie, quantity=Decimal("10"), user=admin_user,
    )

    assert movement.reason == ProcessedMaterialMovementReason.WASTE
    assert expense is None


@pytest.mark.django_db
def test_record_waste_blocked_when_insufficient(ganache, admin_user):
    from apps.core.exceptions import InsufficientStock

    _seed_stock(ganache, Decimal("20"), admin_user)
    with pytest.raises(InsufficientStock):
        services.record_waste(
            processed_material=ganache, quantity=Decimal("50"), user=admin_user,
        )
    # And nothing was booked.
    assert Expense.objects.filter(
        category__name=INVENTORY_WRITE_OFF_CATEGORY
    ).count() == 0


@pytest.mark.django_db
def test_record_waste_rejects_zero_quantity(ganache, admin_user):
    _seed_stock(ganache, Decimal("100"), admin_user)
    with pytest.raises(ValueError):
        services.record_waste(
            processed_material=ganache, quantity=Decimal("0"), user=admin_user,
        )
