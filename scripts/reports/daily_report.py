#!/usr/bin/env python3
r"""Daily operations report for the pastry shop.

Pulls one calendar day from the Adminator API and prints five sections:

1. **Sales summary** — total takings, receipt count, average order value, and
   the best- and slowest-selling items of the day (by units).
2. **Production vs sales** — per product, how many units were baked against how
   many were sold, with a waste % (units produced that didn't sell that day).
3. **Cash report** — sales split by payment method, total expenses, and a cash
   drawer reconciliation (expected vs counted vs difference).
4. **Revenue & profit** — the day's revenue (sales + other income), cost of
   goods sold, gross profit / margin, and net profit before labour (net of
   operating expenses). Labour isn't tracked per day, so it's excluded.
5. **Money available** — the live balance of every active wallet and their sum
   ("total money available"). These are *current* balances, not as of the
   report date — wallet balances aren't snapshotted historically.

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
    # Inventory write-offs are non-cash waste, not spending — keep them out of
    # the expense / cash totals and report them on their own line.
    expenses, write_offs = rc.split_write_offs(
        rc.expenses_between(store.expenses(), day, day)
    )
    expense_txns = rc.transactions_between(store.transactions(), day, day, direction="expense")
    income_txns = rc.transactions_between(store.transactions(), day, day, direction="income")

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
    write_off_total = sum((rc.D(e["amount"]) for e in write_offs), rc.ZERO)
    cash_expenses = sum(
        (rc.D(e["amount"]) for e in expenses if e.get("wallet_name") == rc.CASH_DRAWER_WALLET),
        rc.ZERO,
    )
    cash_expenses += sum(
        (rc.D(t["amount"]) for t in expense_txns if t.get("wallet_name") == rc.CASH_DRAWER_WALLET),
        rc.ZERO,
    )

    expected_cash = rc.D(opening_float) + cash_sales - cash_expenses
    difference = None if counted_cash is None else rc.D(counted_cash) - expected_cash

    # 4 ── revenue & profit ───────────────────────────────────────────────────
    # Mirrors the monthly P&L on a single day: gross profit = sales − COGS;
    # net profit (before labour, which the app doesn't track per day) also
    # nets off the day's other income and operating expenses.
    income_total = rc.transaction_total(income_txns)
    revenue_total = total + income_total
    cost_of_goods = rc.cogs(sales)
    gross_profit = total - cost_of_goods
    gross_margin = rc.pct(gross_profit, total)
    net_profit = revenue_total - cost_of_goods - total_expenses

    # 5 ── money available ────────────────────────────────────────────────────
    # Sum of every active wallet's live balance. Note this is the balance *now*,
    # not as of `day` — wallet balances aren't snapshotted historically.
    wallets = [w for w in store.wallets() if w.get("is_active", True)]
    wallet_rows = [
        {"name": w.get("name", "(unnamed)"), "balance": rc.D(w.get("current_balance"))}
        for w in wallets
    ]
    wallet_rows.sort(key=lambda r: -r["balance"])
    money_available = sum((r["balance"] for r in wallet_rows), rc.ZERO)

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
            "write_offs": write_off_total,
            "write_off_count": len(write_offs),
            "opening_float": rc.D(opening_float),
            "cash_sales": cash_sales,
            "cash_expenses": cash_expenses,
            "expected_cash": expected_cash,
            "counted_cash": None if counted_cash is None else rc.D(counted_cash),
            "difference": difference,
        },
        "profit": {
            "sales": total,
            "other_income": income_total,
            "revenue": revenue_total,
            "cost_of_goods_sold": cost_of_goods,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin,
            "operating_expenses": total_expenses,
            "net_profit": net_profit,
        },
        "money_available": {
            "total": money_available,
            "wallets": wallet_rows,
        },
    }


def render(report: dict, doc, currency: str) -> None:
    M = lambda v: rc.money(v, currency)

    doc.header("DAILY REPORT", f"Date: {report['date']}")

    s = report["sales_summary"]
    doc.section("1. Sales summary")
    doc.kv("Total sales", M(s["total_sales"]))
    doc.kv("Transactions", rc.num(s["transactions"]))
    doc.kv("Average order value", M(s["average_order_value"]) if s["average_order_value"] is not None else "n/a")
    if s["best_selling"]:
        b = s["best_selling"]
        doc.kv("Best-selling item", f"{b['product']}  ({rc.qty(b['units'])} units, {M(b['revenue'])})")
    if s["slowest_selling"]:
        w = s["slowest_selling"]
        doc.kv("Slowest-selling item", f"{w['product']}  ({rc.qty(w['units'])} units, {M(w['revenue'])})")
    if not s["best_selling"]:
        doc.text("  (no sales on this day)")

    p = report["production"]
    doc.section("2. Production vs sales")
    rows = [
        [r["product"], rc.qty(r["produced"]), rc.qty(r["sold"]),
         rc.qty(r["waste_units"]), rc.percent(r["waste_pct"])]
        for r in p["rows"]
    ]
    doc.table(
        ["Product", "Produced", "Sold", "Waste", "Waste %"],
        rows,
        aligns=["l", "r", "r", "r", "r"],
    )
    if p["rows"]:
        doc.text()
        doc.kv("Total produced", rc.qty(p["total_produced"]))
        doc.kv("Total sold", rc.qty(p["total_sold"]))
        doc.kv("Overall waste", rc.percent(p["overall_waste_pct"]))

    c = report["cash"]
    doc.section("3. Cash report")
    doc.text("  Sales per payment method:")
    doc.table(
        ["Method", "Revenue", "Receipts"],
        [[m["method"], M(m["revenue"]), rc.num(m["receipts"])] for m in c["by_payment_method"]],
        aligns=["l", "r", "r"],
    )
    doc.text()
    doc.kv("Total expenses", M(c["total_expenses"]))
    if c["write_offs"]:
        doc.kv("Inventory write-offs",
               f"{M(c['write_offs'])}  ({rc.num(c['write_off_count'])} item(s), non-cash — excluded above)")
    doc.text()
    doc.text("  Cash drawer reconciliation:")
    doc.kv("  Opening float", M(c["opening_float"]))
    doc.kv("  + Cash sales", M(c["cash_sales"]))
    doc.kv("  - Cash expenses", M(c["cash_expenses"]))
    doc.kv("  = Expected in drawer", M(c["expected_cash"]))
    doc.kv("  Counted", M(c["counted_cash"]) if c["counted_cash"] is not None else "n/a (pass --counted-cash)")
    if c["difference"] is None:
        doc.kv("  Difference", "n/a")
    else:
        verdict = "balanced" if c["difference"] == 0 else ("over" if c["difference"] > 0 else "short")
        doc.kv("  Difference", f"{rc.signed_money(c['difference'], currency)}  ({verdict})")
    doc.text()

    pr = report["profit"]
    doc.section("4. Revenue & profit")
    doc.kv("Sales", M(pr["sales"]))
    doc.kv("+ Other income", M(pr["other_income"]))
    doc.kv("= Revenue", M(pr["revenue"]))
    doc.text()
    doc.kv("- Cost of goods sold", M(pr["cost_of_goods_sold"]))
    doc.kv("= Gross profit", rc.signed_money(pr["gross_profit"], currency))
    doc.kv("  Gross margin", rc.percent(pr["gross_margin_pct"]))
    doc.text()
    doc.kv("- Operating expenses", M(pr["operating_expenses"]))
    doc.kv("= Net profit (before labour)", rc.signed_money(pr["net_profit"], currency))

    ma = report["money_available"]
    doc.section("5. Money available")
    doc.text("  Balance per wallet (current, not as of report date):")
    doc.table(
        ["Wallet", "Balance"],
        [[w["name"], M(w["balance"])] for w in ma["wallets"]],
        aligns=["l", "r"],
    )
    doc.text()
    doc.kv("Total money available", M(ma["total"]))
    doc.text()


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
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        render(report, doc, args.currency)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        render(report, rc.TerminalDoc(), args.currency)
    return 0


if __name__ == "__main__":
    sys.exit(main())
