"""Smoke tests for processed-material write-offs.

The recipe / batch flow already has implicit coverage through analytics tests;
this module focuses on the write-off path. Waste is a non-cash inventory event:
it decrements stock but does not book a finance Expense (mirroring the
inventory.services version).
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
def test_record_waste_decrements_without_expense(ganache, admin_user):
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
    # Waste is non-cash: no P&L expense is booked.
    assert expense is None


@pytest.mark.django_db
def test_record_waste_never_creates_expense(ganache, admin_user):
    _seed_stock(ganache, Decimal("500"), admin_user)

    services.record_waste(
        processed_material=ganache, quantity=Decimal("50"), user=admin_user,
    )
    services.record_waste(
        processed_material=ganache, quantity=Decimal("30"), user=admin_user,
    )

    # The (legacy) write-off category and any expense rows stay absent.
    assert not ExpenseCategory.objects.filter(
        name=INVENTORY_WRITE_OFF_CATEGORY
    ).exists()
    assert Expense.objects.count() == 0


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
