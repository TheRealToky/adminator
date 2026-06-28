#!/usr/bin/env python3
r"""Daily operations report for the pastry shop.

Pulls one calendar day from the Adminator API and prints three sections:

1. **Sales summary** — total takings, receipt count, average order value, and
   the best- and slowest-selling items of the day (by units).
2. **Production vs sales** — per product, how many units were baked against how
   many were sold, with a waste % (units produced that didn't sell that day).
3. **Cash report** — sales split by payment method, total expenses, and a cash
   drawer reconciliation (expected vs counted vs difference).

The drawer reconciliation needs the physical count, which the app doesn't hold,
so pass it in: ``--counted-cash`` is what you actually counted in the till, and
``--opening-float`` is the float you started the day with (default 0). Expected
cash = opening float + cash-method sales − cash-method expenses. The non-cash
methods (mobile money, card, bank) settle electronically, so they need no count.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/daily_report.py                       # latest day with sales
    python scripts/daily_report.py --date 2026-06-26
    python scripts/daily_report.py --date 2026-06-26 --counted-cash 84500 --opening-float 20000
    python scripts/daily_report.py --date 2026-06-26 --json
"""
from __future__ import annotations

import sys

import report_common as rc


def best_and_slowest(prod_sales: dict):
    """Return (best, slowest) product rows by units sold, or (None, None)."""
    if not prod_sales:
        return None, None
    ranked = sorted(prod_sales.items(), key=lambda kv: (kv[1]["units"], kv[1]["revenue"]))
    return ranked[-1], ranked[0]


def build_report(store: rc.DataStore, day, counted_cash, opening_float):
    sales = rc.sales_between(store.sales(), day, day)
    runs = rc.completed_runs_between(store.runs(), day, day)
    expenses = rc.expenses_between(store.expenses(), day, day)
    expense_txns = rc.transactions_between(store.transactions(), day, day, direction="expense")

    # 1 ── sales summary ──────────────────────────────────────────────────────
    total = rc.revenue(sales)
    receipts = len(sales)
    aov = rc.safe_div(total, receipts)
    prod_sales = rc.product_sales(sales)
    best, slowest = best_and_slowest(prod_sales)

    # 2 ── production vs sales ────────────────────────────────────────────────
    prod_made = rc.product_production(runs)
    sold_units = {pid: row["units"] for pid, row in prod_sales.items()}
    made_units = {pid: row["units"] for pid, row in prod_made.items()}
    names = {pid: row["name"] for pid, row in {**prod_sales, **prod_made}.items()}

    prod_rows = []
    total_made = rc.ZERO
    total_sold = rc.ZERO
    for pid in sorted(names, key=lambda p: (-made_units.get(p, rc.ZERO), names[p])):
        made = made_units.get(pid, rc.ZERO)
        sold = sold_units.get(pid, rc.ZERO)
        total_made += made
        total_sold += sold
        waste = made - sold
        waste_pct = rc.pct(waste, made) if made > 0 else None
        prod_rows.append({
            "product": names[pid], "produced": made, "sold": sold,
            "waste_units": waste, "waste_pct": waste_pct,
        })
    overall_waste_pct = rc.pct(total_made - total_sold, total_made) if total_made > 0 else None

    # 3 ── cash report ────────────────────────────────────────────────────────
    pay = rc.payment_breakdown(sales)
    cash_sales = pay.get("cash", {}).get("revenue", rc.ZERO)
    total_expenses = rc.expense_total(expenses, expense_txns)
    cash_expenses = sum(
        (rc.D(e["amount"]) for e in expenses if e.get("payment_method") == "cash"), rc.ZERO
    )
    cash_expenses += sum(
        (rc.D(t["amount"]) for t in expense_txns if t.get("payment_method") == "cash"), rc.ZERO
    )

    expected_cash = rc.D(opening_float) + cash_sales - cash_expenses
    difference = None if counted_cash is None else rc.D(counted_cash) - expected_cash

    return {
        "date": day.isoformat(),
        "sales_summary": {
            "total_sales": total,
            "transactions": receipts,
            "average_order_value": aov,
            "best_selling": None if best is None else {
                "product": best[1]["name"], "units": best[1]["units"], "revenue": best[1]["revenue"],
            },
            "slowest_selling": None if slowest is None else {
                "product": slowest[1]["name"], "units": slowest[1]["units"], "revenue": slowest[1]["revenue"],
            },
        },
        "production": {
            "rows": prod_rows,
            "total_produced": total_made,
            "total_sold": total_sold,
            "overall_waste_pct": overall_waste_pct,
        },
        "cash": {
            "by_payment_method": [
                {"method": m, "revenue": v["revenue"], "receipts": v["receipts"]}
                for m, v in sorted(pay.items(), key=lambda kv: -kv[1]["revenue"])
            ],
            "total_expenses": total_expenses,
            "opening_float": rc.D(opening_float),
            "cash_sales": cash_sales,
            "cash_expenses": cash_expenses,
            "expected_cash": expected_cash,
            "counted_cash": None if counted_cash is None else rc.D(counted_cash),
            "difference": difference,
        },
    }


def render(report: dict, currency: str) -> None:
    M = lambda v: rc.money(v, currency)

    rc.header("DAILY REPORT", f"Date: {report['date']}")

    s = report["sales_summary"]
    rc.section("1. Sales summary")
    rc.kv("Total sales", M(s["total_sales"]))
    rc.kv("Transactions", rc.num(s["transactions"]))
    rc.kv("Average order value", M(s["average_order_value"]) if s["average_order_value"] is not None else "n/a")
    if s["best_selling"]:
        b = s["best_selling"]
        rc.kv("Best-selling item", f"{b['product']}  ({rc.qty(b['units'])} units, {M(b['revenue'])})")
    if s["slowest_selling"]:
        w = s["slowest_selling"]
        rc.kv("Slowest-selling item", f"{w['product']}  ({rc.qty(w['units'])} units, {M(w['revenue'])})")
    if not s["best_selling"]:
        print("  (no sales on this day)")

    p = report["production"]
    rc.section("2. Production vs sales")
    rows = [
        [r["product"], rc.qty(r["produced"]), rc.qty(r["sold"]),
         rc.qty(r["waste_units"]), rc.percent(r["waste_pct"])]
        for r in p["rows"]
    ]
    rc.table(
        ["Product", "Produced", "Sold", "Waste", "Waste %"],
        rows,
        aligns=["l", "r", "r", "r", "r"],
    )
    if p["rows"]:
        print()
        rc.kv("Total produced", rc.qty(p["total_produced"]))
        rc.kv("Total sold", rc.qty(p["total_sold"]))
        rc.kv("Overall waste", rc.percent(p["overall_waste_pct"]))

    c = report["cash"]
    rc.section("3. Cash report")
    print("  Sales per payment method:")
    rc.table(
        ["Method", "Revenue", "Receipts"],
        [[m["method"], M(m["revenue"]), rc.num(m["receipts"])] for m in c["by_payment_method"]],
        aligns=["l", "r", "r"],
    )
    print()
    rc.kv("Total expenses", M(c["total_expenses"]))
    print()
    print("  Cash drawer reconciliation:")
    rc.kv("  Opening float", M(c["opening_float"]))
    rc.kv("  + Cash sales", M(c["cash_sales"]))
    rc.kv("  - Cash expenses", M(c["cash_expenses"]))
    rc.kv("  = Expected in drawer", M(c["expected_cash"]))
    rc.kv("  Counted", M(c["counted_cash"]) if c["counted_cash"] is not None else "n/a (pass --counted-cash)")
    if c["difference"] is None:
        rc.kv("  Difference", "n/a")
    else:
        verdict = "balanced" if c["difference"] == 0 else ("over" if c["difference"] > 0 else "short")
        rc.kv("  Difference", f"{rc.signed_money(c['difference'], currency)}  ({verdict})")
    print()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser("Daily sales / production / cash report for Adminator.")
    p.add_argument("--date", help="Day to report (YYYY-MM-DD). Default: latest day with sales.")
    p.add_argument("--counted-cash", type=str, default=None,
                   help="Cash physically counted in the till at close (for reconciliation).")
    p.add_argument("--opening-float", type=str, default="0",
                   help="Cash float the drawer started the day with (default 0).")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    if args.date:
        day = rc.parse_date(args.date)
    else:
        all_sales = store.sales()
        if not all_sales:
            sys.exit("No sales found in the system.")
        day = max(rc.sale_date(s) for s in all_sales)

    counted = None if args.counted_cash is None else rc.D(args.counted_cash)
    report = build_report(store, day, counted, args.opening_float)

    if args.json:
        rc.emit(report)
    else:
        render(report, args.currency)
    return 0


if __name__ == "__main__":
    sys.exit(main())
