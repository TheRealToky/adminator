"""Tests for the wallet register: balance maths, transfers, and the API."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.finance.models import (
    Expense,
    ExpenseCategory,
    Transaction,
    TransactionCategory,
    Wallet,
    WalletEntry,
    WalletEntryType,
)
from apps.finance.views import build_wallet_ledger
from apps.sales.models import Sale


@pytest.fixture
def cash_wallet(db) -> Wallet:
    return Wallet.objects.create(
        name="Cash drawer", account_type="cash", opening_balance=Decimal("1000"),
    )


@pytest.fixture
def bank_wallet(db) -> Wallet:
    return Wallet.objects.create(
        name="Bank account", account_type="bank", opening_balance=Decimal("5000"),
    )


@pytest.mark.django_db
def test_current_balance_starts_at_opening(cash_wallet):
    assert cash_wallet.current_balance == Decimal("1000.00")


@pytest.mark.django_db
def test_deposits_and_withdrawals_move_balance(cash_wallet):
    WalletEntry.objects.create(
        wallet=cash_wallet, entry_type=WalletEntryType.DEPOSIT, amount=Decimal("250"),
    )
    WalletEntry.objects.create(
        wallet=cash_wallet, entry_type=WalletEntryType.WITHDRAWAL, amount=Decimal("100"),
    )
    assert cash_wallet.current_balance == Decimal("1150.00")


@pytest.mark.django_db
def test_signed_amount_sign(cash_wallet):
    deposit = WalletEntry.objects.create(
        wallet=cash_wallet, entry_type=WalletEntryType.DEPOSIT, amount=Decimal("10"),
    )
    withdrawal = WalletEntry.objects.create(
        wallet=cash_wallet, entry_type=WalletEntryType.WITHDRAWAL, amount=Decimal("10"),
    )
    assert deposit.signed_amount == Decimal("10")
    assert withdrawal.signed_amount == Decimal("-10")


@pytest.mark.django_db
def test_transfer_creates_linked_pair_and_moves_money(auth_client, cash_wallet, bank_wallet):
    url = f"/api/v1/finance/wallets/{cash_wallet.id}/transfer/"
    resp = auth_client.post(
        url, {"destination": str(bank_wallet.id), "amount": "300"}, format="json"
    )
    assert resp.status_code == 201

    cash_wallet.refresh_from_db()
    bank_wallet.refresh_from_db()
    assert cash_wallet.current_balance == Decimal("700.00")
    assert bank_wallet.current_balance == Decimal("5300.00")

    out_entry = WalletEntry.objects.get(
        wallet=cash_wallet, entry_type=WalletEntryType.TRANSFER_OUT
    )
    in_entry = WalletEntry.objects.get(
        wallet=bank_wallet, entry_type=WalletEntryType.TRANSFER_IN
    )
    # Both legs share a transfer group and reference each other.
    assert out_entry.transfer_group == in_entry.transfer_group
    assert out_entry.counterparty_wallet_id == bank_wallet.id
    assert in_entry.counterparty_wallet_id == cash_wallet.id


@pytest.mark.django_db
def test_transfer_to_same_wallet_rejected(auth_client, cash_wallet):
    url = f"/api/v1/finance/wallets/{cash_wallet.id}/transfer/"
    resp = auth_client.post(
        url, {"destination": str(cash_wallet.id), "amount": "50"}, format="json"
    )
    assert resp.status_code == 400
    assert not WalletEntry.objects.exists()


@pytest.mark.django_db
def test_deposit_endpoint_records_entry(auth_client, cash_wallet):
    url = f"/api/v1/finance/wallets/{cash_wallet.id}/deposit/"
    resp = auth_client.post(url, {"amount": "75.50"}, format="json")
    assert resp.status_code == 201
    assert resp.data["current_balance"] == "1075.50"
    entry = WalletEntry.objects.get(wallet=cash_wallet)
    assert entry.entry_type == WalletEntryType.DEPOSIT
    assert entry.recorded_by is not None


@pytest.mark.django_db
def test_linked_flows_drive_balance(cash_wallet):
    """A sale (in), an expense (out) and income/expense transactions all move
    the wallet balance without any manual ledger entry."""
    Sale.objects.create(
        receipt_number="R-T-1", subtotal=Decimal("500"), total=Decimal("500"),
        wallet=cash_wallet,
    )
    inc_cat = TransactionCategory.objects.create(name="Tips", direction="income")
    exp_cat = TransactionCategory.objects.create(name="Fees", direction="expense")
    Transaction.objects.create(
        direction="income", category=inc_cat, title="Tip jar",
        amount=Decimal("50"), wallet=cash_wallet,
    )
    Transaction.objects.create(
        direction="expense", category=exp_cat, title="Bank fee",
        amount=Decimal("30"), wallet=cash_wallet,
    )
    ec = ExpenseCategory.objects.create(name="Supplies")
    Expense.objects.create(
        category=ec, title="Napkins", amount=Decimal("120"), wallet=cash_wallet,
    )

    # opening 1000 + 500 sale + 50 income - 30 tx expense - 120 expense = 1400
    assert cash_wallet.current_balance == Decimal("1400.00")


@pytest.mark.django_db
def test_ledger_merges_all_sources(cash_wallet):
    WalletEntry.objects.create(
        wallet=cash_wallet, entry_type=WalletEntryType.DEPOSIT, amount=Decimal("200"),
    )
    Sale.objects.create(
        receipt_number="R-T-2", subtotal=Decimal("300"), total=Decimal("300"),
        wallet=cash_wallet,
    )
    ec = ExpenseCategory.objects.create(name="Supplies")
    Expense.objects.create(
        category=ec, title="Boxes", amount=Decimal("40"), wallet=cash_wallet,
    )

    ledger = build_wallet_ledger(cash_wallet)
    by_source = {row["source"]: row for row in ledger}
    assert set(by_source) == {"manual", "sale", "expense"}
    assert by_source["sale"]["direction"] == "in"
    assert by_source["expense"]["direction"] == "out"
