"""The starter chart of accounts and helpers to resolve posting accounts.

Codes follow the usual convention: 1xxx assets, 2xxx liabilities, 3xxx equity,
4xxx income, 5xxx expenses. Tailored to a manufacturing/retail food business
(raw materials → processed materials → finished goods → sales).
"""
from __future__ import annotations

from apps.ledger.models import Account, AccountType

# ── Well-known account codes (referenced by the posting rules) ─────────────
CASH_ON_HAND = "1000"            # generic cash / undeposited funds (no wallet)
ACCOUNTS_RECEIVABLE = "1100"
INVENTORY_RAW = "1200"
INVENTORY_PROCESSED = "1210"
INVENTORY_FINISHED = "1220"
PREPAID_EXPENSES = "1300"
FIXED_ASSETS_COST = "1500"
ACCUM_DEPRECIATION = "1590"

ACCOUNTS_PAYABLE = "2000"
ACCRUED_EXPENSES = "2100"
DEFERRED_REVENUE = "2200"
TAXES_PAYABLE = "2300"

OWNERS_CAPITAL = "3000"
RETAINED_EARNINGS = "3100"
OWNERS_DRAWINGS = "3900"
OPENING_BALANCE_EQUITY = "3999"

SALES_REVENUE = "4000"
OTHER_INCOME = "4100"
SALES_DISCOUNTS = "4900"

COGS = "5000"
MATERIALS_WASTE = "5100"
OPERATING_EXPENSES = "5200"       # parent; per-category leaves hang off this
DEPRECIATION_EXPENSE = "5300"
INVENTORY_ADJUSTMENT = "5400"
UNCATEGORIZED_EXPENSE = "5900"

# ── The chart: (code, name, type, subtype, parent_code) ────────────────────
CHART: list[tuple[str, str, str, str, str | None]] = [
    # Assets
    (CASH_ON_HAND, "Cash on hand", AccountType.ASSET, "current_asset", None),
    (ACCOUNTS_RECEIVABLE, "Accounts receivable", AccountType.ASSET, "current_asset", None),
    (INVENTORY_RAW, "Inventory – raw materials", AccountType.ASSET, "inventory", None),
    (INVENTORY_PROCESSED, "Inventory – processed materials", AccountType.ASSET, "inventory", None),
    (INVENTORY_FINISHED, "Inventory – finished goods", AccountType.ASSET, "inventory", None),
    (PREPAID_EXPENSES, "Prepaid expenses", AccountType.ASSET, "current_asset", None),
    (FIXED_ASSETS_COST, "Fixed assets – cost", AccountType.ASSET, "fixed_asset", None),
    (ACCUM_DEPRECIATION, "Accumulated depreciation", AccountType.ASSET, "contra_asset", None),
    # Liabilities
    (ACCOUNTS_PAYABLE, "Accounts payable", AccountType.LIABILITY, "current_liability", None),
    (ACCRUED_EXPENSES, "Accrued expenses", AccountType.LIABILITY, "current_liability", None),
    (DEFERRED_REVENUE, "Deferred revenue", AccountType.LIABILITY, "current_liability", None),
    (TAXES_PAYABLE, "Taxes payable", AccountType.LIABILITY, "current_liability", None),
    # Equity
    (OWNERS_CAPITAL, "Owner's capital", AccountType.EQUITY, "equity", None),
    (RETAINED_EARNINGS, "Retained earnings", AccountType.EQUITY, "equity", None),
    (OWNERS_DRAWINGS, "Owner's drawings", AccountType.EQUITY, "equity", None),
    (OPENING_BALANCE_EQUITY, "Opening balance equity", AccountType.EQUITY, "equity", None),
    # Income
    (SALES_REVENUE, "Sales revenue", AccountType.INCOME, "operating_income", None),
    (OTHER_INCOME, "Other income", AccountType.INCOME, "other_income", None),
    (SALES_DISCOUNTS, "Sales discounts", AccountType.INCOME, "contra_income", None),
    # Expenses
    (COGS, "Cost of goods sold", AccountType.EXPENSE, "cogs", None),
    (MATERIALS_WASTE, "Materials waste / spoilage", AccountType.EXPENSE, "operating_expense", None),
    (OPERATING_EXPENSES, "Operating expenses", AccountType.EXPENSE, "operating_expense", None),
    (DEPRECIATION_EXPENSE, "Depreciation expense", AccountType.EXPENSE, "operating_expense", None),
    (INVENTORY_ADJUSTMENT, "Inventory adjustments", AccountType.EXPENSE, "operating_expense", None),
    (UNCATEGORIZED_EXPENSE, "Uncategorized expense", AccountType.EXPENSE, "operating_expense", None),
]

# Parent accounts should not receive postings directly.
NON_POSTABLE_CODES = {OPERATING_EXPENSES}


def seed_chart_of_accounts() -> int:
    """Create any missing accounts from CHART. Idempotent. Returns #created."""
    created = 0
    # First pass: create/refresh the flat accounts.
    for code, name, type_, subtype, _parent in CHART:
        obj, was_created = Account.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "type": type_,
                "subtype": subtype,
                "is_postable": code not in NON_POSTABLE_CODES,
            },
        )
        created += int(was_created)
    # Second pass: wire parents once every code exists.
    by_code = {a.code: a for a in Account.objects.all()}
    for code, _name, _type, _subtype, parent_code in CHART:
        if parent_code and by_code[code].parent_id != by_code[parent_code].id:
            by_code[code].parent = by_code[parent_code]
            by_code[code].save(update_fields=["parent", "updated_at"])
    return created


# ── Runtime account resolution used by the posting rules ───────────────────
def account(code: str) -> Account:
    """Fetch a fixed account by code, creating the chart lazily if needed."""
    try:
        return Account.objects.get(code=code)
    except Account.DoesNotExist:
        seed_chart_of_accounts()
        return Account.objects.get(code=code)


def cash_account_for_wallet(wallet) -> Account:
    """Return the cash sub-account for a wallet, creating one on first use.

    Wallets get their own leaf under the 1000 range (``1000-<n>``) so each
    wallet's GL balance can be reconciled against its live ``current_balance``.
    A ``None`` wallet falls back to the generic 'Cash on hand' account.
    """
    if wallet is None:
        return account(CASH_ON_HAND)
    existing = Account.objects.filter(wallet=wallet).first()
    if existing:
        return existing
    # Allocate a stable, readable code after the generic cash account.
    n = Account.objects.filter(code__startswith="1000-").count() + 1
    return Account.objects.create(
        code=f"1000-{n}",
        name=f"Cash · {wallet.name}",
        type=AccountType.ASSET,
        subtype="current_asset",
        wallet=wallet,
    )


def expense_account_for_category(category) -> Account:
    """Return the operating-expense leaf for an ExpenseCategory (create lazily)."""
    if category is None:
        return account(UNCATEGORIZED_EXPENSE)
    existing = Account.objects.filter(expense_category=category).first()
    if existing:
        return existing
    n = Account.objects.filter(code__startswith="5200-").count() + 1
    return Account.objects.create(
        code=f"5200-{n}",
        name=f"Expenses · {category.name}",
        type=AccountType.EXPENSE,
        subtype="operating_expense",
        parent=account(OPERATING_EXPENSES),
        expense_category=category,
    )
