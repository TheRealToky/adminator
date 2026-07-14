"""Financial statements built from the ledger.

All three statements sum ``JournalLine`` rows of *posted* entries — never the
legacy domain aggregates. That is the whole point of the GL: one set of numbers
that must balance.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from . import chart_of_accounts as coa
from .models import (
    ZERO,
    Account,
    AccountType,
    BALANCE_SHEET_TYPES,
    EntryStatus,
    JournalLine,
)


def _posted_lines(*, start=None, end=None):
    qs = JournalLine.objects.filter(entry__status=EntryStatus.POSTED)
    if start is not None:
        qs = qs.filter(entry__date__gte=start)
    if end is not None:
        qs = qs.filter(entry__date__lte=end)
    return qs


def _account_totals(*, start=None, end=None) -> dict[str, dict]:
    """Per-account (debit, credit) sums over the window, keyed by account id."""
    rows = (
        _posted_lines(start=start, end=end)
        .values("account_id")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    return {
        str(r["account_id"]): {
            "debit": r["debit"] or ZERO,
            "credit": r["credit"] or ZERO,
        }
        for r in rows
    }


def trial_balance(as_of=None) -> dict:
    """Every account's debit/credit totals up to ``as_of`` (inclusive).

    The two column totals must be equal — that equality is the ledger's
    self-check. A non-zero ``difference`` means something posted unbalanced.
    """
    as_of = as_of or timezone.localdate()
    totals = _account_totals(end=as_of)

    accounts = Account.objects.all().order_by("code")
    lines = []
    total_debit = total_credit = ZERO
    for acc in accounts:
        t = totals.get(str(acc.id))
        if not t:
            continue
        debit, credit = t["debit"], t["credit"]
        balance = debit - credit  # positive = net debit
        lines.append({
            "account_code": acc.code,
            "account_name": acc.name,
            "type": acc.type,
            "debit": debit,
            "credit": credit,
            "balance": balance,
        })
        total_debit += debit
        total_credit += credit

    return {
        "as_of": as_of.isoformat(),
        "lines": lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": total_debit - total_credit,
        "balanced": total_debit == total_credit,
    }


def _net_by_type(totals: dict[str, dict], acc_types) -> tuple[list[dict], Decimal]:
    """Natural-signed balances for accounts of the given type(s)."""
    accounts = Account.objects.filter(type__in=acc_types).order_by("code")
    out, subtotal = [], ZERO
    for acc in accounts:
        t = totals.get(str(acc.id))
        if not t:
            continue
        signed = t["debit"] - t["credit"]
        # Present each account as a positive natural balance.
        natural = signed if acc.is_debit_normal else -signed
        out.append({
            "account_code": acc.code,
            "account_name": acc.name,
            "amount": natural,
        })
        subtotal += natural
    return out, subtotal


def income_statement(start, end) -> dict:
    """Accrual P&L for the [start, end] window (inclusive)."""
    totals = _account_totals(start=start, end=end)

    income, total_income = _net_by_type(totals, [AccountType.INCOME])
    expenses, total_expense = _net_by_type(totals, [AccountType.EXPENSE])

    # Split COGS out of expenses for a gross-profit line.
    cogs_total = next(
        (row["amount"] for row in expenses if row["account_code"] == coa.COGS), ZERO
    )
    gross_profit = total_income - cogs_total
    net_profit = total_income - total_expense

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "income": income,
        "total_income": total_income,
        "cost_of_goods_sold": cogs_total,
        "gross_profit": gross_profit,
        "expenses": expenses,
        "total_expenses": total_expense,
        "net_profit": net_profit,
    }


def balance_sheet(as_of=None) -> dict:
    """Assets = Liabilities + Equity as at ``as_of``.

    Retained earnings for the current year (net income to date) is folded into
    equity so the sheet balances without a period-close having been run.
    """
    as_of = as_of or timezone.localdate()
    totals = _account_totals(end=as_of)

    assets, total_assets = _net_by_type(totals, [AccountType.ASSET])
    liabilities, total_liabilities = _net_by_type(totals, [AccountType.LIABILITY])
    equity, total_equity = _net_by_type(totals, [AccountType.EQUITY])

    # Net income to date (income − expense) accumulates into equity.
    _, total_income = _net_by_type(totals, [AccountType.INCOME])
    _, total_expense = _net_by_type(totals, [AccountType.EXPENSE])
    current_earnings = total_income - total_expense

    equity_total_with_earnings = total_equity + current_earnings
    equity_side = total_liabilities + equity_total_with_earnings

    return {
        "as_of": as_of.isoformat(),
        "assets": assets,
        "total_assets": total_assets,
        "liabilities": liabilities,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "current_year_earnings": current_earnings,
        "total_equity": equity_total_with_earnings,
        "total_liabilities_and_equity": equity_side,
        "balanced": total_assets == equity_side,
    }
