#!/usr/bin/env python3
r"""Weekly performance report for the pastry shop.

Reports a 7-day window (ending on ``--week-ending``, default the latest day with
sales) in four sections:

1. **Revenue performance** — this week vs the previous week vs the average of the
   trailing ``--avg-weeks`` weeks (default 4), with the week-on-week change.
2. **Product performance** — per product: units sold, revenue and margin %
   (``(revenue − COGS) ÷ revenue`` using the cost snapshot taken at sale time).
3. **Cost tracking** — ingredients cost ÷ sales, i.e. cost of goods sold over
   revenue for the week.
4. **Operations KPIs** — waste rate, production accuracy, delivery delays,
   employee hours per 1,000 revenue, and customer complaints.

Three of those KPIs are not modelled in the app, so they are supplied from
outside and otherwise show ``n/a``:

* ``--labor-hours``  (env ``ADMINATOR_LABOR_HOURS_WEEKLY``) — staff hours worked.
* ``--complaints``   (env ``ADMINATOR_COMPLAINTS_WEEKLY``) — customer complaints.
* ``--delivery-delays`` (env ``ADMINATOR_DELIVERY_DELAYS_WEEKLY``) — late
  deliveries; the count of delivery-channel receipts is shown for context.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/weekly_report.py
    python scripts/weekly_report.py --week-ending 2026-06-26 --avg-weeks 4
    python scripts/weekly_report.py --week-ending 2026-06-26 --labor-hours 240 --complaints 3
    python scripts/weekly_report.py --week-ending 2026-06-26 --json
"""
from __future__ import annotations

import sys
from datetime import timedelta

import report_common as rc


def week_revenue(sales: list, transactions: list, start, end) -> rc.Decimal:
    """Revenue = receipt takings + manual income transactions in the window
    (matches how the app's dashboard KPI defines revenue)."""
    sale_total = rc.revenue(rc.sales_between(sales, start, end))
    income = rc.transaction_total(
        rc.transactions_between(transactions, start, end, direction="income")
    )
    return sale_total + income


def build_report(store, end, avg_weeks, labor_hours, complaints, delivery_delays):
    sales_all = store.sales()
    txns_all = store.transactions()
    runs_all = store.runs()

    start, end = rc.week_bounds(end)
    prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)

    this_rev = week_revenue(sales_all, txns_all, start, end)
    prev_rev = week_revenue(sales_all, txns_all, prev_start, prev_end)

    # Trailing average over the avg_weeks complete weeks ending at `end`.
    weekly_totals = []
    for w in range(avg_weeks):
        w_end = end - timedelta(days=7 * w)
        w_start = w_end - timedelta(days=6)
        weekly_totals.append(week_revenue(sales_all, txns_all, w_start, w_end))
    avg_rev = sum(weekly_totals, rc.ZERO) / len(weekly_totals) if weekly_totals else rc.ZERO

    wow_change = rc.pct(this_rev - prev_rev, prev_rev)
    vs_avg = rc.pct(this_rev - avg_rev, avg_rev)

    # ── product performance ──────────────────────────────────────────────────
    week_sales = rc.sales_between(sales_all, start, end)
    prod = rc.product_sales(week_sales)
    product_rows = []
    for pid, row in sorted(prod.items(), key=lambda kv: -kv[1]["revenue"]):
        margin = rc.pct(row["revenue"] - row["cost"], row["revenue"])
        product_rows.append({
            "product": row["name"], "units": row["units"],
            "revenue": row["revenue"], "margin_pct": margin,
        })

    # ── cost tracking: COGS ÷ sales ──────────────────────────────────────────
    sales_total = rc.revenue(week_sales)
    week_cogs = rc.cogs(week_sales)
    cogs_ratio = rc.pct(week_cogs, sales_total)

    # ── operations KPIs ──────────────────────────────────────────────────────
    runs = rc.completed_runs_between(runs_all, start, end)
    units_produced = sum((rc.D(r["quantity"]) for r in runs), rc.ZERO)
    units_sold = sum((row["units"] for row in prod.values()), rc.ZERO)
    waste_rate = rc.pct(units_produced - units_sold, units_produced)
    # Production accuracy: how closely output tracked demand, penalising both
    # over- and under-production. 100% means produced == sold.
    if units_produced > 0:
        miss = abs(units_produced - units_sold)
        accuracy = max(rc.ZERO, (rc.D(1) - miss / units_produced) * 100)
    else:
        accuracy = None

    delivery_receipts = sum(1 for s in week_sales if s.get("channel") == "delivery")
    hours_per_1k = (
        rc.safe_div(labor_hours, sales_total / 1000) if labor_hours is not None else None
    )

    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "revenue_performance": {
            "this_week": this_rev,
            "previous_week": prev_rev,
            "weekly_average": avg_rev,
            "avg_weeks": avg_weeks,
            "wow_change_pct": wow_change,
            "vs_average_pct": vs_avg,
        },
        "product_performance": product_rows,
        "cost_tracking": {
            "sales": sales_total,
            "ingredients_cost": week_cogs,
            "cogs_to_sales_pct": cogs_ratio,
        },
        "operations_kpis": {
            "units_produced": units_produced,
            "units_sold": units_sold,
            "waste_rate_pct": waste_rate,
            "production_accuracy_pct": accuracy,
            "delivery_receipts": delivery_receipts,
            "delivery_delays": delivery_delays,
            "labor_hours": labor_hours,
            "employee_hours_per_1k_revenue": hours_per_1k,
            "customer_complaints": complaints,
        },
    }


def render(report: dict, doc, currency: str, top: int) -> None:
    M = lambda v: rc.money(v, currency)

    doc.header("WEEKLY REPORT", f"Week: {report['week_start']} → {report['week_end']}")

    r = report["revenue_performance"]
    doc.section("1. Revenue performance")
    doc.kv("This week", M(r["this_week"]))
    doc.kv("Previous week", M(r["previous_week"]))
    doc.kv(f"Average (last {r['avg_weeks']} wks)", M(r["weekly_average"]))
    doc.kv("Week-on-week change", rc.percent(r["wow_change_pct"]))
    doc.kv("vs weekly average", rc.percent(r["vs_average_pct"]))

    doc.section("2. Product performance")
    rows = report["product_performance"]
    shown = rows[:top] if top else rows
    doc.table(
        ["Product", "Units", "Revenue", "Margin %"],
        [[x["product"], rc.qty(x["units"]), M(x["revenue"]), rc.percent(x["margin_pct"])]
         for x in shown],
        aligns=["l", "r", "r", "r"],
    )
    if top and len(rows) > top:
        doc.text(f"  … {len(rows) - top} more product(s) (use --top 0 to show all)")

    c = report["cost_tracking"]
    doc.section("3. Cost tracking")
    doc.kv("Sales (revenue)", M(c["sales"]))
    doc.kv("Ingredients cost (COGS)", M(c["ingredients_cost"]))
    doc.kv("Ingredients ÷ sales", rc.percent(c["cogs_to_sales_pct"]))

    k = report["operations_kpis"]
    doc.section("4. Operations KPIs")
    doc.kv("Units produced", rc.qty(k["units_produced"]))
    doc.kv("Units sold", rc.qty(k["units_sold"]))
    doc.kv("Waste rate", rc.percent(k["waste_rate_pct"]))
    doc.kv("Production accuracy", rc.percent(k["production_accuracy_pct"]))
    delays = "n/a (not tracked — pass --delivery-delays)" if k["delivery_delays"] is None \
        else f"{rc.num(k['delivery_delays'])} late of {rc.num(k['delivery_receipts'])} delivery receipt(s)"
    doc.kv("Delivery delays", delays)
    if k["employee_hours_per_1k_revenue"] is not None:
        doc.kv("Employee hours / 1,000 rev",
               f"{rc.num(k['employee_hours_per_1k_revenue'], 2)} hrs  ({rc.num(k['labor_hours'])} hrs total)")
    else:
        doc.kv("Employee hours / 1,000 rev", "n/a (pass --labor-hours)")
    doc.kv("Customer complaints",
           rc.num(k["customer_complaints"]) if k["customer_complaints"] is not None
           else "n/a (pass --complaints)")
    doc.text()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser("Weekly performance report for Adminator.")
    p.add_argument("--week-ending", help="Last day of the week (YYYY-MM-DD). Default: latest day with sales.")
    p.add_argument("--avg-weeks", type=int, default=4, help="Weeks to average for the baseline (default 4).")
    p.add_argument("--top", type=int, default=15, help="Show only the top N products by revenue (0 = all).")
    p.add_argument("--labor-hours", type=str, default=None,
                   help="Staff hours worked this week (else env ADMINATOR_LABOR_HOURS_WEEKLY).")
    p.add_argument("--complaints", type=str, default=None,
                   help="Customer complaints this week (else env ADMINATOR_COMPLAINTS_WEEKLY).")
    p.add_argument("--delivery-delays", type=str, default=None,
                   help="Late deliveries this week (else env ADMINATOR_DELIVERY_DELAYS_WEEKLY).")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    if args.week_ending:
        end = rc.parse_date(args.week_ending)
    else:
        all_sales = store.sales()
        if not all_sales:
            sys.exit("No sales found in the system.")
        end = max(rc.sale_date(s) for s in all_sales)

    labor_hours = rc.resolve_optional(args.labor_hours, "ADMINATOR_LABOR_HOURS_WEEKLY")
    complaints = rc.resolve_optional(args.complaints, "ADMINATOR_COMPLAINTS_WEEKLY")
    delivery_delays = rc.resolve_optional(args.delivery_delays, "ADMINATOR_DELIVERY_DELAYS_WEEKLY")

    report = build_report(store, end, max(1, args.avg_weeks),
                          labor_hours, complaints, delivery_delays)

    if args.json:
        rc.emit(report)
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        render(report, doc, args.currency, args.top)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        render(report, rc.TerminalDoc(), args.currency, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
