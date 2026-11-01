#!/usr/bin/env python3
r"""Average daily expenses over a date window.

Answers "what do we spend on an average day?" between a start and end date, in
total and per day, with a breakdown by category.

What counts as an expense
-------------------------
The same definition the weekly report uses, so the two reconcile:

* **recorded expenses** (``/finance/expenses/``), bucketed by ``incurred_on``;
* **manual expense-direction transactions** (``/finance/transactions/`` with
  ``direction = expense``), bucketed by ``occurred_on`` — this includes salary
  payouts, which are spending like any other.

**Inventory write-offs are excluded.** A write-off is a non-cash accounting move
(wasted stock, no money left the till), so counting it as a daily expense would
overstate what the shop actually spent. Historic data still carries these rows;
they are summed on their own line for reference and kept out of every average.

Averaging and the denominator
------------------------------
Two averages, because they answer different questions:

* **per calendar day** — total expenses divided by *every* day in the window,
  including days nothing was spent. This is the headline figure and the direct
  answer to "average daily expenses": it tells you the daily run-rate you need
  to cover over the whole period.
* **per day with expenses** — divided only by the days that actually recorded a
  cash expense. Always the higher of the two; useful when spending is lumpy
  (e.g. a weekly supplier run) and you want the size of a typical spending day
  rather than the smoothed run-rate.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/expense_daily_average.py --start 2026-06-01 --end 2026-06-30
    python scripts/expense_daily_average.py --start 2026-06-01 --end 2026-06-30 --daily
    python scripts/expense_daily_average.py --json
    python scripts/expense_daily_average.py --start 2026-06-01 --end 2026-06-30 --docx expenses.docx
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

# report_common lives in scripts/reports/; make this script importable no matter
# the working directory or shell, so `python scripts/expense_daily_average.py`
# just works without setting PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))

import report_common as rc

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]

UNCATEGORISED = "(uncategorised)"


def day_range(start, end):
    """Every calendar day from ``start`` to ``end`` inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def expense_dates(store: rc.DataStore) -> list[date]:
    """Every date that carries a cash expense — recorded expenses (excluding
    write-offs) plus expense-direction transactions — used to default the
    window to the span of the data, the same way the other reports default
    theirs to the sales span."""
    dates = [
        date.fromisoformat(e["incurred_on"])
        for e in store.expenses() if not rc.is_write_off(e)
    ]
    dates += [
        date.fromisoformat(t["occurred_on"])
        for t in store.transactions() if t.get("direction") == "expense"
    ]
    return dates


def _flatten(real_expenses: list, expense_txns: list) -> list[dict]:
    """Recorded expenses + expense transactions in one common shape.

    Both are cash out, so they are pooled exactly as the weekly report pools
    them, keyed to the field each source dates itself by (``incurred_on`` for
    expenses, ``occurred_on`` for transactions).
    """
    items = []
    for e in real_expenses:
        items.append({
            "date": date.fromisoformat(e["incurred_on"]),
            "category": e.get("category_name") or UNCATEGORISED,
            "amount": rc.D(e["amount"]),
        })
    for t in expense_txns:
        items.append({
            "date": date.fromisoformat(t["occurred_on"]),
            "category": t.get("category_name") or UNCATEGORISED,
            "amount": rc.D(t["amount"]),
        })
    return items


def build_report(store: rc.DataStore, start, end):
    real, write_offs = rc.split_write_offs(
        rc.expenses_between(store.expenses(), start, end)
    )
    expense_txns = rc.transactions_between(
        store.transactions(), start, end, direction="expense"
    )
    items = _flatten(real, expense_txns)

    calendar_days = list(day_range(start, end))
    per_day = {d: rc.ZERO for d in calendar_days}
    for it in items:
        per_day[it["date"]] += it["amount"]
    days_with_expenses = [d for d, amt in per_day.items() if amt > 0]

    total = rc.expense_total(real, expense_txns)
    write_off_total = sum((rc.D(e["amount"]) for e in write_offs), rc.ZERO)

    # Category breakdown — where the money went, biggest first.
    by_cat: dict[str, dict] = {}
    for it in items:
        row = by_cat.setdefault(
            it["category"],
            {"category": it["category"], "amount": rc.ZERO, "count": 0},
        )
        row["amount"] += it["amount"]
        row["count"] += 1
    category_rows = sorted(by_cat.values(), key=lambda r: (-r["amount"], r["category"]))
    for r in category_rows:
        r["share_pct"] = rc.pct(r["amount"], total)

    daily_rows = [
        {"date": d, "weekday": WEEKDAYS[d.weekday()], "amount": per_day[d],
         "spent": per_day[d] > 0}
        for d in calendar_days
    ]
    spending_days = [r for r in daily_rows if r["spent"]]
    highest = max(spending_days, key=lambda r: r["amount"], default=None)

    return {
        "window": {
            "start": start,
            "end": end,
            "calendar_days": len(calendar_days),
            "days_with_expenses": len(days_with_expenses),
        },
        "totals": {
            "total_expenses": total,
            "item_count": len(items),
            "avg_per_calendar_day": rc.safe_div(total, len(calendar_days)),
            "avg_per_day_with_expenses": rc.safe_div(total, len(days_with_expenses)),
            "highest_day": None if highest is None else
                {"date": highest["date"], "amount": highest["amount"]},
            "write_offs": write_off_total,
            "write_off_count": len(write_offs),
        },
        "by_category": category_rows,
        "daily": daily_rows,
    }


def render(report: dict, doc, currency: str, show_daily: bool) -> None:
    M = lambda v: rc.money(v, currency)
    w = report["window"]
    t = report["totals"]

    doc.header(
        "AVERAGE DAILY EXPENSES",
        f"{w['start'].isoformat()} to {w['end'].isoformat()}  "
        f"({w['calendar_days']} calendar days, "
        f"{rc.num(w['days_with_expenses'])} with spending)",
    )

    doc.section("1. Averages")
    doc.kv("Total expenses", M(t["total_expenses"]))
    doc.kv("Expense items", rc.num(t["item_count"]))
    doc.text()
    doc.kv("Avg / calendar day", M(t["avg_per_calendar_day"])
           if t["avg_per_calendar_day"] is not None else "n/a")
    doc.kv("Avg / day with expenses", M(t["avg_per_day_with_expenses"])
           if t["avg_per_day_with_expenses"] is not None else "n/a")
    if t["highest_day"]:
        h = t["highest_day"]
        doc.kv("Highest spending day", f"{h['date'].isoformat()}  ({M(h['amount'])})")
    if t["write_offs"]:
        doc.text()
        doc.kv("Inventory write-offs",
               f"{M(t['write_offs'])}  ({rc.num(t['write_off_count'])} item(s), "
               "non-cash — excluded from the averages)")

    doc.section("2. By category")
    doc.table(
        ["Category", "Items", "Total", "Share"],
        [
            [c["category"], rc.num(c["count"]), M(c["amount"]),
             rc.percent(c["share_pct"])]
            for c in report["by_category"]
        ],
        aligns=["l", "r", "r", "r"],
    )

    if show_daily:
        doc.section("3. Day by day")
        doc.table(
            ["Date", "Weekday", "Expenses"],
            [
                [r["date"].isoformat(), r["weekday"],
                 M(r["amount"]) if r["spent"] else "-"]
                for r in report["daily"]
            ],
            aligns=["l", "l", "r"],
        )
    doc.text()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser(
        "Average daily expenses for Adminator over a date window, with a "
        "category breakdown."
    )
    p.add_argument("--start", help="First day of the window (YYYY-MM-DD). "
                                   "Default: earliest recorded expense.")
    p.add_argument("--end", help="Last day of the window (YYYY-MM-DD). "
                                 "Default: latest recorded expense.")
    p.add_argument("--daily", action="store_true",
                   help="Also print the day-by-day expense totals.")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    if args.start and args.end:
        start, end = rc.parse_date(args.start), rc.parse_date(args.end)
    else:
        dates = expense_dates(store)
        if not dates:
            sys.exit("No expenses found in the system.")
        start = rc.parse_date(args.start) if args.start else min(dates)
        end = rc.parse_date(args.end) if args.end else max(dates)
    if start > end:
        sys.exit(f"--start ({start}) is after --end ({end}).")

    report = build_report(store, start, end)

    if args.json:
        rc.emit(report)
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        render(report, doc, args.currency, args.daily)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        render(report, rc.TerminalDoc(), args.currency, args.daily)
    return 0


if __name__ == "__main__":
    sys.exit(main())
