"""Tests for the double-entry general ledger.

Posting normally runs in shadow mode (errors swallowed). These tests flip
shadow mode OFF via the ``strict_ledger`` fixture so any imbalance or bug raises
loudly instead of hiding.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finance.models import (
    Expense,
    ExpenseCategory,
    Invoice,
    InvoiceStatus,
    Transaction,
    TransactionCategory,
    TransactionDirection,
    Wallet,
)
from apps.catalog.models import Product, ProductCategory, RawMaterial, RecipeItem
from apps.finance.models import Asset, AssetStatus
from apps.inventory import services as inventory_services
from apps.inventory.models import MovementReason
from apps.ledger import chart_of_accounts as coa
from apps.ledger import posting_rules, reports
from apps.ledger.models import (
    Account,
    AccountingPeriod,
    EntryStatus,
    JournalEntry,
    PeriodStatus,
)
from apps.ledger.posting import Leg, LedgerError, post, post_source
from apps.processed_materials import services as pm_services
from apps.processed_materials.models import (
    ProcessedMaterial,
    ProcessedMaterialRecipeItem,
)
from apps.production import services as production_services
from apps.sales.models import PaymentMethod, Sale


@pytest.fixture
def strict_ledger(settings):
    """Make posting errors fatal for the duration of a test."""
    settings.LEDGER_POSTING_ENABLED = True
    settings.LEDGER_SHADOW_MODE = False
    return settings


@pytest.fixture
def chart(db):
    coa.seed_chart_of_accounts()


@pytest.fixture
def wallet(db):
    return Wallet.objects.create(
        name="Cash drawer", account_type="cash", opening_balance=Decimal("0")
    )


def _make_sale(**kwargs) -> Sale:
    defaults = dict(
        receipt_number=f"R-{timezone.now().timestamp()}",
        occurred_at=timezone.now(),
        payment_method=PaymentMethod.CASH,
        subtotal=Decimal("1000"),
        discount=Decimal("0"),
        total=Decimal("1000"),
        cost_of_goods=Decimal("600"),
    )
    defaults.update(kwargs)
    return Sale.objects.create(**defaults)


# ── Chart of accounts ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_seed_chart_is_idempotent(chart):
    first = Account.objects.count()
    coa.seed_chart_of_accounts()
    assert Account.objects.count() == first
    assert Account.objects.filter(code=coa.SALES_REVENUE).exists()


@pytest.mark.django_db
def test_operating_expenses_parent_is_not_postable(chart):
    assert Account.objects.get(code=coa.OPERATING_EXPENSES).is_postable is False


# ── Posting engine ───────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_unbalanced_entry_is_rejected(chart):
    with pytest.raises(LedgerError):
        post(
            date=timezone.localdate(),
            legs=[
                Leg.dr(coa.account(coa.CASH_ON_HAND), Decimal("100")),
                Leg.cr(coa.account(coa.SALES_REVENUE), Decimal("90")),
            ],
        )


@pytest.mark.django_db
def test_leg_cannot_be_both_debit_and_credit(chart):
    with pytest.raises(LedgerError):
        post(
            date=timezone.localdate(),
            legs=[
                Leg(account=coa.account(coa.CASH_ON_HAND),
                    debit=Decimal("10"), credit=Decimal("10")),
                Leg.cr(coa.account(coa.SALES_REVENUE), Decimal("10")),
            ],
        )


@pytest.mark.django_db
def test_post_source_replaces_prior_entry(chart):
    kwargs = dict(
        source_type="test.Thing", source_id="abc", event="x",
        date=timezone.localdate(),
    )
    post_source(legs=[
        Leg.dr(coa.account(coa.CASH_ON_HAND), Decimal("100")),
        Leg.cr(coa.account(coa.SALES_REVENUE), Decimal("100")),
    ], **kwargs)
    post_source(legs=[
        Leg.dr(coa.account(coa.CASH_ON_HAND), Decimal("250")),
        Leg.cr(coa.account(coa.SALES_REVENUE), Decimal("250")),
    ], **kwargs)

    live = JournalEntry.objects.filter(
        source_type="test.Thing", source_id="abc", event="x",
        status=EntryStatus.POSTED,
    )
    assert live.count() == 1
    assert live.first().total_debit == Decimal("250")


# ── Sales posting ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_cash_sale_debits_cash_and_credits_revenue(strict_ledger, chart, wallet):
    sale = _make_sale(wallet=wallet)

    revenue = JournalEntry.objects.get(source_id=str(sale.id), event="revenue")
    cash_acc = coa.cash_account_for_wallet(wallet)
    debit_line = revenue.lines.get(account=cash_acc)
    assert debit_line.debit == Decimal("1000")
    assert revenue.is_balanced

    cogs = JournalEntry.objects.get(source_id=str(sale.id), event="cogs")
    assert cogs.lines.get(account=coa.account(coa.COGS)).debit == Decimal("600")
    assert cogs.lines.get(account=coa.account(coa.INVENTORY_FINISHED)).credit == Decimal("600")


@pytest.mark.django_db
def test_credit_sale_debits_receivable_not_cash(strict_ledger, chart, wallet):
    """The core cash→accrual fix: a credit sale must NOT touch cash."""
    sale = _make_sale(wallet=wallet, payment_method=PaymentMethod.CREDIT)

    revenue = JournalEntry.objects.get(source_id=str(sale.id), event="revenue")
    ar = coa.account(coa.ACCOUNTS_RECEIVABLE)
    assert revenue.lines.get(account=ar).debit == Decimal("1000")
    # No cash leg at all.
    cash_acc = coa.cash_account_for_wallet(wallet)
    assert not revenue.lines.filter(account=cash_acc).exists()


@pytest.mark.django_db
def test_discounted_sale_books_contra_revenue(strict_ledger, chart, wallet):
    sale = _make_sale(
        wallet=wallet, subtotal=Decimal("1000"),
        discount=Decimal("100"), total=Decimal("900"),
    )
    revenue = JournalEntry.objects.get(source_id=str(sale.id), event="revenue")
    assert revenue.lines.get(account=coa.account(coa.SALES_REVENUE)).credit == Decimal("1000")
    assert revenue.lines.get(account=coa.account(coa.SALES_DISCOUNTS)).debit == Decimal("100")
    assert revenue.is_balanced


@pytest.mark.django_db
def test_editing_sale_reposts_single_entry(strict_ledger, chart, wallet):
    sale = _make_sale(wallet=wallet)
    sale.total = Decimal("1500")
    sale.subtotal = Decimal("1500")
    sale.save()

    live = JournalEntry.objects.filter(
        source_id=str(sale.id), event="revenue", status=EntryStatus.POSTED
    )
    assert live.count() == 1
    assert live.first().total_debit == Decimal("1500")


@pytest.mark.django_db
def test_deleting_sale_reverses_entries(strict_ledger, chart, wallet):
    sale = _make_sale(wallet=wallet)
    sale_id = sale.id
    sale.delete()
    assert not JournalEntry.objects.filter(
        source_id=str(sale_id), status=EntryStatus.POSTED
    ).exists()


# ── Expenses & transactions ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_expense_posts_expense_and_cash(strict_ledger, chart, wallet):
    cat = ExpenseCategory.objects.create(name="Utilities")
    exp = Expense.objects.create(
        category=cat, title="Electricity", amount=Decimal("200"),
        incurred_on=timezone.localdate(), wallet=wallet,
    )
    entry = JournalEntry.objects.get(source_id=str(exp.id), event="expense")
    exp_acc = coa.expense_account_for_category(cat)
    assert entry.lines.get(account=exp_acc).debit == Decimal("200")
    assert entry.lines.get(account=coa.cash_account_for_wallet(wallet)).credit == Decimal("200")


@pytest.mark.django_db
def test_income_transaction_posts_other_income(strict_ledger, chart, wallet):
    cat = TransactionCategory.objects.create(
        name="Grant", direction=TransactionDirection.INCOME
    )
    txn = Transaction.objects.create(
        direction=TransactionDirection.INCOME, category=cat, title="Grant",
        amount=Decimal("500"), occurred_on=timezone.localdate(), wallet=wallet,
    )
    entry = JournalEntry.objects.get(source_id=str(txn.id))
    assert entry.lines.get(account=coa.account(coa.OTHER_INCOME)).credit == Decimal("500")
    assert entry.lines.get(account=coa.cash_account_for_wallet(wallet)).debit == Decimal("500")


# ── Invoices (accounts receivable) ───────────────────────────────────────────
def _make_invoice(**kwargs) -> Invoice:
    defaults = dict(
        invoice_number=f"INV-{timezone.now().timestamp()}",
        customer_name="Acme Co",
        issue_date=timezone.localdate(),
        due_date=timezone.localdate() + timedelta(days=30),
        amount=Decimal("5000"),
        amount_paid=Decimal("0"),
        status=InvoiceStatus.SENT,
    )
    defaults.update(kwargs)
    return Invoice.objects.create(**defaults)


@pytest.mark.django_db
def test_issued_invoice_recognizes_receivable(strict_ledger, chart):
    inv = _make_invoice()
    revenue = JournalEntry.objects.get(source_id=str(inv.id), event="revenue")
    assert revenue.lines.get(account=coa.account(coa.ACCOUNTS_RECEIVABLE)).debit == Decimal("5000")
    assert revenue.lines.get(account=coa.account(coa.SALES_REVENUE)).credit == Decimal("5000")


@pytest.mark.django_db
def test_draft_invoice_posts_nothing(strict_ledger, chart):
    inv = _make_invoice(status=InvoiceStatus.DRAFT)
    assert not JournalEntry.objects.filter(
        source_id=str(inv.id), status=EntryStatus.POSTED
    ).exists()


@pytest.mark.django_db
def test_invoice_payment_settles_receivable(strict_ledger, chart):
    inv = _make_invoice()
    inv.amount_paid = Decimal("2000")
    inv.status = InvoiceStatus.PARTIALLY_PAID
    inv.paid_at = timezone.now()
    inv.save()

    settlement = JournalEntry.objects.get(source_id=str(inv.id), event="settlement")
    assert settlement.lines.get(account=coa.account(coa.CASH_ON_HAND)).debit == Decimal("2000")
    assert settlement.lines.get(account=coa.account(coa.ACCOUNTS_RECEIVABLE)).credit == Decimal("2000")
    # Net A/R for this invoice = 5000 issued − 2000 settled = 3000 still owed.


@pytest.mark.django_db
def test_cancelling_invoice_reverses_receivable(strict_ledger, chart):
    inv = _make_invoice()
    assert JournalEntry.objects.filter(source_id=str(inv.id), event="revenue").exists()
    inv.status = InvoiceStatus.CANCELLED
    inv.save()
    assert not JournalEntry.objects.filter(
        source_id=str(inv.id), event="revenue", status=EntryStatus.POSTED
    ).exists()


# ── Reports ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_trial_balance_is_balanced(strict_ledger, chart, wallet):
    _make_sale(wallet=wallet)
    _make_sale(wallet=wallet, payment_method=PaymentMethod.CREDIT)
    tb = reports.trial_balance()
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


@pytest.mark.django_db
def test_income_statement_matches_sale(strict_ledger, chart, wallet):
    _make_sale(wallet=wallet)  # revenue 1000, cogs 600
    today = timezone.localdate()
    pl = reports.income_statement(start=today - timedelta(days=1), end=today)
    assert pl["total_income"] == Decimal("1000")
    assert pl["cost_of_goods_sold"] == Decimal("600")
    assert pl["gross_profit"] == Decimal("400")
    assert pl["net_profit"] == Decimal("400")


@pytest.mark.django_db
def test_balance_sheet_balances(strict_ledger, chart, wallet):
    _make_sale(wallet=wallet)
    bs = reports.balance_sheet()
    assert bs["balanced"] is True
    assert bs["total_assets"] == bs["total_liabilities_and_equity"]


# ── Periods ──────────────────────────────────────────────────────────────────
# ── Expenses on credit (accounts payable) ────────────────────────────────────
@pytest.mark.django_db
def test_credit_expense_posts_to_accounts_payable(strict_ledger, chart, wallet):
    cat = ExpenseCategory.objects.create(name="Supplies")
    exp = Expense.objects.create(
        category=cat, title="Flour delivery", amount=Decimal("300"),
        incurred_on=timezone.localdate(), wallet=wallet, on_credit=True,
    )
    entry = JournalEntry.objects.get(source_id=str(exp.id), event="expense")
    assert entry.lines.get(account=coa.account(coa.ACCOUNTS_PAYABLE)).credit == Decimal("300")
    # No cash moved while the bill is outstanding.
    assert not entry.lines.filter(account=coa.cash_account_for_wallet(wallet)).exists()
    assert not JournalEntry.objects.filter(
        source_id=str(exp.id), event="settlement", status=EntryStatus.POSTED
    ).exists()


@pytest.mark.django_db
def test_settling_credit_expense_posts_settlement(strict_ledger, chart, wallet):
    cat = ExpenseCategory.objects.create(name="Supplies")
    exp = Expense.objects.create(
        category=cat, title="Flour delivery", amount=Decimal("300"),
        incurred_on=timezone.localdate(), wallet=wallet, on_credit=True,
    )
    exp.settled_at = timezone.localdate()
    exp.save()

    settlement = JournalEntry.objects.get(source_id=str(exp.id), event="settlement")
    assert settlement.lines.get(account=coa.account(coa.ACCOUNTS_PAYABLE)).debit == Decimal("300")
    assert settlement.lines.get(account=coa.cash_account_for_wallet(wallet)).credit == Decimal("300")


# ── Inventory value posting ──────────────────────────────────────────────────
@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name="Bakery")


def _raw(name="Flour", unit_cost="2"):
    return RawMaterial.objects.create(
        sku=f"RM-{name}-{timezone.now().timestamp()}", name=name, unit="g",
        unit_cost=Decimal(unit_cost),
    )


def _product_with_recipe(category, raw, qty_per_unit="100"):
    product = Product.objects.create(
        sku=f"P-{timezone.now().timestamp()}", name="Loaf", category=category,
        selling_price=Decimal("500"),
    )
    RecipeItem.objects.create(product=product, raw_material=raw, quantity=Decimal(qty_per_unit))
    return product


@pytest.mark.django_db
def test_raw_purchase_capitalises_inventory_against_payable(strict_ledger, chart):
    flour = _raw(unit_cost="2")
    movement = inventory_services.receive_raw_material(
        raw_material=flour, quantity=Decimal("1000")
    )
    entry = JournalEntry.objects.get(source_id=str(movement.id), event="purchase")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_RAW)).debit == Decimal("2000")
    assert entry.lines.get(account=coa.account(coa.ACCOUNTS_PAYABLE)).credit == Decimal("2000")


@pytest.mark.django_db
def test_raw_waste_charges_materials_waste(strict_ledger, chart):
    flour = _raw(unit_cost="2")
    inventory_services.receive_raw_material(raw_material=flour, quantity=Decimal("100"))
    movement, _ = inventory_services.record_waste(
        raw_material=flour, quantity=Decimal("10")
    )
    entry = JournalEntry.objects.get(source_id=str(movement.id), event="waste")
    assert entry.lines.get(account=coa.account(coa.MATERIALS_WASTE)).debit == Decimal("20")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_RAW)).credit == Decimal("20")


@pytest.mark.django_db
def test_stock_adjustment_posts_to_adjustment_account(strict_ledger, chart):
    flour = _raw(unit_cost="2")
    stock = inventory_services.ensure_stock_item(raw_material=flour)
    movement = inventory_services.adjust_stock(
        stock_item=stock, quantity_delta=Decimal("5"),
        reason=MovementReason.ADJUSTMENT_IN,
    )
    entry = JournalEntry.objects.get(source_id=str(movement.id), event="adjustment_in")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_RAW)).debit == Decimal("10")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_ADJUSTMENT)).credit == Decimal("10")


@pytest.mark.django_db
def test_production_run_moves_raw_to_finished(strict_ledger, chart, category):
    flour = _raw(unit_cost="2")
    product = _product_with_recipe(category, flour, qty_per_unit="100")
    inventory_services.receive_raw_material(raw_material=flour, quantity=Decimal("1000"))

    run = production_services.execute_production(product=product, quantity=Decimal("5"))
    # 5 loaves × 100g × 2 = 1000 of raw value capitalised into finished goods.
    entry = JournalEntry.objects.get(source_id=str(run.id), event="production")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_FINISHED)).debit == Decimal("1000")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_RAW)).credit == Decimal("1000")


@pytest.mark.django_db
def test_processed_batch_capitalises_processed_inventory(strict_ledger, chart):
    flour = _raw(unit_cost="2")
    inventory_services.receive_raw_material(raw_material=flour, quantity=Decimal("1000"))
    dough = ProcessedMaterial.objects.create(
        sku=f"PM-{timezone.now().timestamp()}", name="Dough", unit="g",
        yield_per_batch=Decimal("10"),
    )
    ProcessedMaterialRecipeItem.objects.create(
        processed_material=dough, raw_material=flour, quantity=Decimal("200")
    )
    batch = pm_services.produce_batch(processed_material=dough, batches=Decimal("1"))
    # 200g × 2 = 400 of raw value capitalised into processed inventory.
    entry = JournalEntry.objects.get(source_id=str(batch.id), event="batch")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_PROCESSED)).debit == Decimal("400")
    assert entry.lines.get(account=coa.account(coa.INVENTORY_RAW)).credit == Decimal("400")


@pytest.mark.django_db
def test_inventory_flow_keeps_trial_balance_balanced(strict_ledger, chart, category):
    flour = _raw(unit_cost="2")
    product = _product_with_recipe(category, flour, qty_per_unit="100")
    inventory_services.receive_raw_material(raw_material=flour, quantity=Decimal("1000"))
    production_services.execute_production(product=product, quantity=Decimal("5"))
    inventory_services.record_waste(raw_material=flour, quantity=Decimal("10"))
    assert reports.trial_balance()["balanced"] is True


# ── Depreciation ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_monthly_depreciation_posts_expense_and_accumulated(strict_ledger, chart):
    asset = Asset.objects.create(
        name="Oven", purchase_date=date(2026, 1, 1),
        purchase_cost=Decimal("1200"), useful_life_months=12,
    )
    posting_rules.post_depreciation(asset, date(2026, 1, 15))
    entry = JournalEntry.objects.get(
        source_id=str(asset.id), event="depreciation:2026-01"
    )
    assert entry.lines.get(account=coa.account(coa.DEPRECIATION_EXPENSE)).debit == Decimal("100")
    assert entry.lines.get(account=coa.account(coa.ACCUM_DEPRECIATION)).credit == Decimal("100")
    assert entry.date == date(2026, 1, 31)


@pytest.mark.django_db
def test_depreciation_last_month_absorbs_rounding(strict_ledger, chart):
    asset = Asset.objects.create(
        name="Mixer", purchase_date=date(2026, 1, 1),
        purchase_cost=Decimal("1000"), useful_life_months=3,
    )
    charges = [
        posting_rules.depreciation_for_month(asset, date(2026, m, 1)) for m in (1, 2, 3)
    ]
    assert charges == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]
    assert sum(charges) == Decimal("1000")
    # Outside the schedule → nothing.
    assert posting_rules.depreciation_for_month(asset, date(2026, 4, 1)) == Decimal("0")


# ── Manual journal entry validation ──────────────────────────────────────────
@pytest.mark.django_db
def test_manual_entry_serializer_rejects_unbalanced(chart):
    from apps.ledger.serializers import ManualJournalEntrySerializer

    s = ManualJournalEntrySerializer(data={
        "date": timezone.localdate().isoformat(),
        "memo": "manual",
        "lines": [
            {"account": str(coa.account(coa.CASH_ON_HAND).id), "debit": "100"},
            {"account": str(coa.account(coa.OWNERS_CAPITAL).id), "credit": "90"},
        ],
    })
    assert not s.is_valid()
    assert "lines" in s.errors


@pytest.mark.django_db
def test_manual_entry_serializer_accepts_balanced(chart):
    from apps.ledger.serializers import ManualJournalEntrySerializer

    s = ManualJournalEntrySerializer(data={
        "date": timezone.localdate().isoformat(),
        "memo": "owner top-up",
        "lines": [
            {"account": str(coa.account(coa.CASH_ON_HAND).id), "debit": "100"},
            {"account": str(coa.account(coa.OWNERS_CAPITAL).id), "credit": "100"},
        ],
    })
    assert s.is_valid(), s.errors


# ── Periods ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_closed_period_blocks_posting(strict_ledger, chart):
    today = timezone.localdate()
    period = AccountingPeriod.for_date(today)
    period.status = PeriodStatus.CLOSED
    period.save(update_fields=["status"])

    with pytest.raises(LedgerError):
        post(
            date=today,
            legs=[
                Leg.dr(coa.account(coa.CASH_ON_HAND), Decimal("10")),
                Leg.cr(coa.account(coa.SALES_REVENUE), Decimal("10")),
            ],
        )
