"""Map domain events to journal entries.

Each ``post_*`` function is idempotent: it can be called on create, on edit, or
during a bulk re-sync and will always converge to the correct entry for that
source. Deletions are handled by :func:`reverse_*`.

Currently wired (Phase 3/4 — shadow mode):
  * Sale         → revenue + (cash | A/R), plus a matched COGS/inventory entry
  * Expense      → operating expense + (cash | A/P), plus A/P settlement
  * Transaction  → income/expense + cash
  * Invoice      → A/R at issuance + cumulative cash settlement
  * StockMovement→ raw purchase (→ A/P), waste, and stock adjustments
  * ProcessedMaterialStockMovement → waste and stock adjustments
  * ProductionRun→ raw/processed inventory → finished goods
  * ProcessedMaterialBatch → raw/sub-processed inventory → processed inventory
  * Asset        → straight-line monthly depreciation (command-driven)

Deferred to later phases (documented in docs/accrual-migration-plan.md):
  asset-purchase capitalisation, deferred revenue for customer deposits, tax on
  sales, and the Phase 5 cutover that makes the GL authoritative.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date as _date
from decimal import Decimal, ROUND_HALF_UP

from . import chart_of_accounts as coa
from .posting import Leg, safe_post_source, safe_reverse_source

ZERO = Decimal("0")
CENTS = Decimal("0.01")


def _as_date(value):
    """Coerce a datetime/date to a plain date (accounting date)."""
    return value.date() if hasattr(value, "date") else value


# ── Sales ──────────────────────────────────────────────────────────────────
def post_sale(sale) -> None:
    """Book revenue (and matched COGS) for a Sale.

    Cash sales debit the wallet's cash account; credit sales
    (``payment_method == 'credit'``) debit Accounts Receivable instead — this is
    the core cash→accrual fix, keeping unpaid sales out of cash.
    """
    if sale.total is None:
        return

    source_type = "sales.Sale"
    date = sale.occurred_at.date() if hasattr(sale.occurred_at, "date") else sale.occurred_at

    total = Decimal(sale.total)
    discount = Decimal(sale.discount or ZERO)

    # A Sale is saved twice (header first, then totals) — and could be fully
    # discounted to zero. Nothing meaningful to post until there's a value; also
    # clear any prior entries if an edit zeroed it out.
    if total <= ZERO:
        reverse_sale(sale.id)
        return

    is_credit = sale.payment_method == "credit"
    debit_account = (
        coa.account(coa.ACCOUNTS_RECEIVABLE)
        if is_credit
        else coa.cash_account_for_wallet(sale.wallet)
    )

    # Revenue entry:  Dr cash/AR (+ Dr discount contra) ; Cr revenue (gross).
    revenue_legs = [
        Leg.dr(debit_account, total, memo=sale.receipt_number, wallet=sale.wallet),
    ]
    if discount > ZERO:
        revenue_legs.append(
            Leg.dr(coa.account(coa.SALES_DISCOUNTS), discount, memo="Discount")
        )
    revenue_legs.append(
        Leg.cr(coa.account(coa.SALES_REVENUE), total + discount, memo=sale.receipt_number)
    )
    safe_post_source(
        source_type=source_type, source_id=sale.id, event="revenue",
        date=date, legs=revenue_legs,
        memo=f"Sale {sale.receipt_number}",
    )

    # COGS entry:  Dr COGS ; Cr Inventory – finished goods.
    cogs = Decimal(sale.cost_of_goods or ZERO)
    if cogs > ZERO:
        safe_post_source(
            source_type=source_type, source_id=sale.id, event="cogs",
            date=date,
            legs=[
                Leg.dr(coa.account(coa.COGS), cogs, memo=sale.receipt_number),
                Leg.cr(coa.account(coa.INVENTORY_FINISHED), cogs, memo=sale.receipt_number),
            ],
            memo=f"COGS {sale.receipt_number}",
        )
    else:
        # Cost may have dropped to zero on an edit — clear a stale COGS entry.
        safe_reverse_source(source_type=source_type, source_id=sale.id, event="cogs")


def reverse_sale(sale_id) -> None:
    safe_reverse_source(source_type="sales.Sale", source_id=sale_id)


# ── Expenses (cash & supplier bills / A/P) ───────────────────────────────────
def post_expense(expense) -> None:
    """Book an expense; on-credit bills route the credit leg to Accounts Payable.

    * Cash expense:      Dr operating expense ; Cr Cash/Wallet.
    * Supplier bill:     Dr operating expense ; Cr Accounts Payable — the expense
      is recognised when incurred, independent of when it's paid.
    * Bill settlement:   once ``settled_at`` is set, a second entry books
      Dr Accounts Payable ; Cr Cash/Wallet on the settlement date. Because
      posting is idempotent, clearing ``settled_at`` reverses that entry.
    """
    source_type = "finance.Expense"
    amount = Decimal(expense.amount or ZERO)
    if amount <= ZERO:
        reverse_expense(expense.id)
        return

    on_credit = bool(getattr(expense, "on_credit", False))
    expense_acc = coa.expense_account_for_category(expense.category)
    cash_acc = coa.cash_account_for_wallet(expense.wallet)
    credit_acc = coa.account(coa.ACCOUNTS_PAYABLE) if on_credit else cash_acc

    # Expense recognition — always exists once there's an amount.
    safe_post_source(
        source_type=source_type, source_id=expense.id, event="expense",
        date=expense.incurred_on,
        legs=[
            Leg.dr(expense_acc, amount, memo=expense.title),
            Leg.cr(credit_acc, amount, memo=expense.title,
                   wallet=None if on_credit else expense.wallet),
        ],
        memo=f"Expense · {expense.title}",
    )

    # Settlement of an on-credit bill — Dr A/P ; Cr Cash on the day it was paid.
    settled_on = getattr(expense, "settled_at", None) if on_credit else None
    if settled_on:
        safe_post_source(
            source_type=source_type, source_id=expense.id, event="settlement",
            date=settled_on,
            legs=[
                Leg.dr(coa.account(coa.ACCOUNTS_PAYABLE), amount, memo=expense.title),
                Leg.cr(cash_acc, amount, memo=expense.title, wallet=expense.wallet),
            ],
            memo=f"Bill payment · {expense.title}",
        )
    else:
        safe_reverse_source(source_type=source_type, source_id=expense.id,
                            event="settlement")


def reverse_expense(expense_id) -> None:
    safe_reverse_source(source_type="finance.Expense", source_id=expense_id)


# ── Manual transactions ──────────────────────────────────────────────────────
def post_transaction(txn) -> None:
    """Book a manual income/expense transaction against a wallet."""
    amount = Decimal(txn.amount or ZERO)
    if amount <= ZERO:
        return

    cash = coa.cash_account_for_wallet(txn.wallet)
    if txn.direction == "income":
        legs = [
            Leg.dr(cash, amount, memo=txn.title, wallet=txn.wallet),
            Leg.cr(coa.account(coa.OTHER_INCOME), amount, memo=txn.title),
        ]
    else:  # expense
        legs = [
            Leg.dr(coa.account(coa.UNCATEGORIZED_EXPENSE), amount, memo=txn.title),
            Leg.cr(cash, amount, memo=txn.title, wallet=txn.wallet),
        ]
    safe_post_source(
        source_type="finance.Transaction", source_id=txn.id, event=txn.direction,
        date=txn.occurred_on, legs=legs, memo=f"Transaction · {txn.title}",
    )


def reverse_transaction(txn_id) -> None:
    safe_reverse_source(source_type="finance.Transaction", source_id=txn_id)


# ── Invoices (accounts receivable) ───────────────────────────────────────────
def post_invoice(invoice) -> None:
    """Integrate a customer Invoice into the GL as accounts receivable.

    Revenue is recognized at issuance (Dr A/R ; Cr Sales revenue) once the
    invoice leaves ``draft`` — that is the accrual point, independent of when
    cash arrives. Payments are booked as a single cumulative settlement entry
    (Dr Cash ; Cr A/R) sized to ``amount_paid``; because posting is idempotent,
    partial payments just re-post the growing total. A draft or cancelled
    invoice carries no revenue, and a fully-unpaid invoice carries no settlement.
    """
    source_type = "finance.Invoice"
    amount = Decimal(invoice.amount or ZERO)
    recognized = invoice.status not in ("draft", "cancelled") and amount > ZERO

    if recognized:
        safe_post_source(
            source_type=source_type, source_id=invoice.id, event="revenue",
            date=invoice.issue_date,
            legs=[
                Leg.dr(coa.account(coa.ACCOUNTS_RECEIVABLE), amount,
                       memo=invoice.invoice_number),
                Leg.cr(coa.account(coa.SALES_REVENUE), amount,
                       memo=invoice.invoice_number),
            ],
            memo=f"Invoice {invoice.invoice_number}",
        )
    else:
        safe_reverse_source(source_type=source_type, source_id=invoice.id, event="revenue")

    paid = Decimal(invoice.amount_paid or ZERO)
    if paid > ZERO and invoice.status != "cancelled":
        pay_date = invoice.paid_at.date() if invoice.paid_at else invoice.issue_date
        safe_post_source(
            source_type=source_type, source_id=invoice.id, event="settlement",
            date=pay_date,
            legs=[
                Leg.dr(coa.cash_account_for_wallet(None), paid,
                       memo=invoice.invoice_number),
                Leg.cr(coa.account(coa.ACCOUNTS_RECEIVABLE), paid,
                       memo=invoice.invoice_number),
            ],
            memo=f"Invoice {invoice.invoice_number} payment",
        )
    else:
        safe_reverse_source(source_type=source_type, source_id=invoice.id, event="settlement")


def reverse_invoice(invoice_id) -> None:
    safe_reverse_source(source_type="finance.Invoice", source_id=invoice_id)


# ── Inventory movements (raw / finished goods) ───────────────────────────────
#
# Movements that belong to a larger document are valued at that document level
# instead (see post_production_run / post_processed_batch), and finished-goods
# drawdown on a Sale is already carried by the COGS entry. So only these
# stand-alone movement reasons post here:
_STOCK_MOVEMENT_EVENTS = {
    "purchase", "waste", "adjustment_in", "adjustment_out",
}


def post_stock_movement(movement) -> None:
    """Value a raw-material / finished-goods StockMovement into the GL.

    * purchase       Dr Inventory ; Cr Accounts Payable (received on credit).
    * waste          Dr Materials waste ; Cr Inventory.
    * adjustment_in  Dr Inventory ; Cr Inventory adjustments.
    * adjustment_out Dr Inventory adjustments ; Cr Inventory.

    Production and sale movements carry no entry here — they are booked at the
    run/batch level and by the sale's COGS entry respectively.
    """
    source_type = "inventory.StockMovement"
    reason = movement.reason
    if reason not in _STOCK_MOVEMENT_EVENTS:
        return

    item = movement.stock_item
    value = (abs(Decimal(movement.quantity_delta)) *
             Decimal(item.item_unit_cost or ZERO)).quantize(CENTS, ROUND_HALF_UP)
    if value <= ZERO:
        safe_reverse_source(source_type=source_type, source_id=movement.id)
        return

    inv_acc = coa.account(
        coa.INVENTORY_RAW if item.kind == "raw_material" else coa.INVENTORY_FINISHED
    )
    legs = _inventory_movement_legs(reason, inv_acc, value, movement.reference)
    if legs is None:
        return
    safe_post_source(
        source_type=source_type, source_id=movement.id, event=reason,
        date=_as_date(movement.created_at), legs=legs,
        memo=f"{movement.get_reason_display()} · {item.item_name}",
    )


def reverse_stock_movement(movement_id) -> None:
    safe_reverse_source(source_type="inventory.StockMovement", source_id=movement_id)


def post_pm_stock_movement(movement) -> None:
    """Value a stand-alone processed-material movement (waste / adjustment).

    Batch production and product-run consumption are booked at the document
    level, so only waste and manual adjustments post here — all against the
    processed-materials inventory account (1210).
    """
    source_type = "processed_materials.ProcessedMaterialStockMovement"
    reason = movement.reason
    if reason not in _STOCK_MOVEMENT_EVENTS:
        return

    stock = movement.stock
    value = (abs(Decimal(movement.quantity_delta)) *
             Decimal(stock.item_unit_cost or ZERO)).quantize(CENTS, ROUND_HALF_UP)
    if value <= ZERO:
        safe_reverse_source(source_type=source_type, source_id=movement.id)
        return

    inv_acc = coa.account(coa.INVENTORY_PROCESSED)
    legs = _inventory_movement_legs(reason, inv_acc, value, movement.reference)
    if legs is None:
        return
    safe_post_source(
        source_type=source_type, source_id=movement.id, event=reason,
        date=_as_date(movement.created_at), legs=legs,
        memo=f"{movement.get_reason_display()} · {stock.item_name}",
    )


def reverse_pm_stock_movement(movement_id) -> None:
    safe_reverse_source(
        source_type="processed_materials.ProcessedMaterialStockMovement",
        source_id=movement_id,
    )


def _inventory_movement_legs(reason, inv_acc, value, reference):
    """Build the two legs for a stand-alone inventory movement (or None to skip)."""
    if reason == "purchase":
        return [
            Leg.dr(inv_acc, value, memo=reference),
            Leg.cr(coa.account(coa.ACCOUNTS_PAYABLE), value, memo=reference),
        ]
    if reason == "waste":
        return [
            Leg.dr(coa.account(coa.MATERIALS_WASTE), value, memo=reference),
            Leg.cr(inv_acc, value, memo=reference),
        ]
    if reason == "adjustment_in":
        return [
            Leg.dr(inv_acc, value, memo=reference),
            Leg.cr(coa.account(coa.INVENTORY_ADJUSTMENT), value, memo=reference),
        ]
    if reason == "adjustment_out":
        return [
            Leg.dr(coa.account(coa.INVENTORY_ADJUSTMENT), value, memo=reference),
            Leg.cr(inv_acc, value, memo=reference),
        ]
    return None


# ── Production runs & processed-material batches ─────────────────────────────
def post_production_run(run) -> None:
    """Capitalise a completed production run into finished-goods inventory.

    Dr Inventory – finished goods ; Cr Inventory – raw materials (+ processed)
    for the value of the inputs consumed. The raw/processed split is recomputed
    from the product's recipe so each inventory account is relieved correctly.
    A non-completed (planned/cancelled) run carries no entry.
    """
    source_type = "production.ProductionRun"
    if run.status != "completed":
        safe_reverse_source(source_type=source_type, source_id=run.id)
        return

    qty = Decimal(run.quantity)
    raw_portion = ZERO
    for item in run.product.recipe_items.select_related("raw_material").all():
        raw_portion += Decimal(item.quantity) * qty * Decimal(item.raw_material.unit_cost)
    processed_portion = ZERO
    for usage in run.product.processed_usages.select_related("processed_material").all():
        processed_portion += (
            Decimal(usage.quantity) * qty * Decimal(usage.processed_material.unit_cost)
        )

    raw_portion = raw_portion.quantize(CENTS, ROUND_HALF_UP)
    processed_portion = processed_portion.quantize(CENTS, ROUND_HALF_UP)
    total = raw_portion + processed_portion
    if total <= ZERO:
        # Recipe unavailable (edited/removed) — fall back to the stored cost so
        # the finished-goods value still lands, charged against raw inventory.
        total = Decimal(run.cost or ZERO).quantize(CENTS, ROUND_HALF_UP)
        raw_portion, processed_portion = total, ZERO
    if total <= ZERO:
        return

    legs = [Leg.dr(coa.account(coa.INVENTORY_FINISHED), total, memo=f"PROD-{run.id}")]
    if raw_portion > ZERO:
        legs.append(Leg.cr(coa.account(coa.INVENTORY_RAW), raw_portion,
                           memo=f"PROD-{run.id}"))
    if processed_portion > ZERO:
        legs.append(Leg.cr(coa.account(coa.INVENTORY_PROCESSED), processed_portion,
                           memo=f"PROD-{run.id}"))
    safe_post_source(
        source_type=source_type, source_id=run.id, event="production",
        date=_as_date(run.completed_at) if run.completed_at else run.scheduled_for,
        legs=legs, memo=f"Production · {run.product.name} × {run.quantity}",
    )


def reverse_production_run(run_id) -> None:
    safe_reverse_source(source_type="production.ProductionRun", source_id=run_id)


def post_processed_batch(batch) -> None:
    """Capitalise a processed-material batch into processed inventory.

    Dr Inventory – processed ; Cr Inventory – raw (+ Inventory – processed for
    any sub-processed ingredients consumed). Split is recomputed from the recipe.
    """
    source_type = "processed_materials.ProcessedMaterialBatch"
    batches = Decimal(batch.batches)
    raw_portion = ZERO
    sub_portion = ZERO
    items = batch.processed_material.recipe_items.select_related(
        "raw_material", "sub_processed_material"
    ).all()
    for item in items:
        line = Decimal(item.quantity) * batches * Decimal(item.ingredient_unit_cost)
        if item.sub_processed_material_id:
            sub_portion += line
        else:
            raw_portion += line

    raw_portion = raw_portion.quantize(CENTS, ROUND_HALF_UP)
    sub_portion = sub_portion.quantize(CENTS, ROUND_HALF_UP)
    total = raw_portion + sub_portion
    if total <= ZERO:
        total = Decimal(batch.cost or ZERO).quantize(CENTS, ROUND_HALF_UP)
        raw_portion, sub_portion = total, ZERO
    if total <= ZERO:
        return

    legs = [Leg.dr(coa.account(coa.INVENTORY_PROCESSED), total,
                   memo=f"PMBATCH-{batch.id}")]
    if raw_portion > ZERO:
        legs.append(Leg.cr(coa.account(coa.INVENTORY_RAW), raw_portion,
                           memo=f"PMBATCH-{batch.id}"))
    if sub_portion > ZERO:
        legs.append(Leg.cr(coa.account(coa.INVENTORY_PROCESSED), sub_portion,
                           memo=f"PMBATCH-{batch.id}"))
    safe_post_source(
        source_type=source_type, source_id=batch.id, event="batch",
        date=_as_date(batch.completed_at) if batch.completed_at else batch.scheduled_for,
        legs=legs, memo=f"Batch · {batch.processed_material.name}",
    )


def reverse_processed_batch(batch_id) -> None:
    safe_reverse_source(
        source_type="processed_materials.ProcessedMaterialBatch", source_id=batch_id
    )


# ── Depreciation (command-driven monthly job) ────────────────────────────────
def depreciation_for_month(asset, month) -> Decimal:
    """Straight-line depreciation charged to ``asset`` for the given month.

    ``month`` is any date in the target month. Depreciation runs for
    ``useful_life_months`` starting the purchase month; the final month absorbs
    the rounding remainder so total charges equal the purchase cost exactly.
    Returns ZERO for months outside the schedule (or non-depreciating assets).
    """
    life = asset.useful_life_months or 0
    if life <= 0:
        return ZERO
    purchase = asset.purchase_date
    index = (month.year - purchase.year) * 12 + (month.month - purchase.month)
    if index < 0 or index >= life:
        return ZERO

    cost = Decimal(asset.purchase_cost)
    per_month = (cost / Decimal(life)).quantize(CENTS, ROUND_HALF_UP)
    if index == life - 1:
        return cost - per_month * (life - 1)   # remainder in the last month
    return per_month


def post_depreciation(asset, month) -> None:
    """Post one month of straight-line depreciation for an asset (idempotent).

    Dr Depreciation expense (5300) ; Cr Accumulated depreciation (1590). Keyed on
    ``(Asset, month)`` so re-running the monthly job never double-charges.
    """
    source_type = "finance.Asset"
    first = month.replace(day=1)
    event = f"depreciation:{first:%Y-%m}"
    amount = depreciation_for_month(asset, first)
    if amount <= ZERO:
        safe_reverse_source(source_type=source_type, source_id=asset.id, event=event)
        return

    last_day = monthrange(first.year, first.month)[1]
    as_of = _date(first.year, first.month, last_day)
    safe_post_source(
        source_type=source_type, source_id=asset.id, event=event,
        date=as_of,
        legs=[
            Leg.dr(coa.account(coa.DEPRECIATION_EXPENSE), amount, memo=asset.name),
            Leg.cr(coa.account(coa.ACCUM_DEPRECIATION), amount, memo=asset.name),
        ],
        memo=f"Depreciation {first:%Y-%m} · {asset.name}",
    )
