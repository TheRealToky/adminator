#!/usr/bin/env python3
r"""Monthly financial report for the pastry shop.

Reports one calendar month (``--month YYYY-MM``, default the month of the latest
day with sales) in three sections:

1. **Profit & Loss**
     * gross profit = sales − cost of goods sold
     * net profit   = revenue − variable costs − fixed costs
   where revenue = sales + manual income, variable costs = COGS, and fixed costs
   = operating expenses + labour.
2. **Key financial ratios**
     * gross margin = (sales − COGS) ÷ sales
     * labour cost ratio = labour ÷ sales
     * waste analysis = total units produced − total units sold (also as a %).
3. **Cash flow**
     * money in  = sales + income
     * money out = total expenses
     * net cash flow = money in − money out

Labour is not modelled in the app, so the month's labour cost is supplied from
outside via ``--labor-cost`` (or env ``ADMINATOR_LABOR_COST_MONTHLY``); when it
is omitted the labour line and ratio read ``n/a`` and net profit is reported
before labour.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/monthly_report.py
    python scripts/monthly_report.py --month 2026-06
    python scripts/monthly_report.py --month 2026-06 --labor-cost 1500000
    python scripts/monthly_report.py --month 2026-06 --json
"""
from __future__ import annotations

import sys

import report_common as rc


def build_report(store, start, end, labor_cost):
    sales = rc.sales_between(store.sales(), start, end)
    income_txns = rc.transactions_between(store.transactions(), start, end, direction="income")
    expense_txns = rc.transactions_between(store.transactions(), start, end, direction="expense")
    expenses = rc.expenses_between(store.expenses(), start, end)
    runs = rc.completed_runs_between(store.runs(), start, end)

    sales_total = rc.revenue(sales)
    income_total = rc.transaction_total(income_txns)
    revenue_total = sales_total + income_total
    cost_of_goods = rc.cogs(sales)
    operating_expenses = rc.expense_total(expenses, expense_txns)

    gross_profit = sales_total - cost_of_goods

    # Variable costs = COGS; fixed costs = operating expenses + labour (if known).
    variable_costs = cost_of_goods
    labor = labor_cost if labor_cost is not None else rc.ZERO
    fixed_costs = operating_expenses + labor
    net_profit = revenue_total - variable_costs - fixed_costs

    # Ratios
    gross_margin = rc.pct(gross_profit, sales_total)
    labor_ratio = rc.pct(labor_cost, sales_total) if labor_cost is not None else None

    units_produced = sum((rc.D(r["quantity"]) for r in runs), rc.ZERO)
    units_sold = sum(
        (rc.D(it["quantity"]) for s in sales for it in s["items"]), rc.ZERO
    )
    waste_units = units_produced - units_sold
    waste_pct = rc.pct(waste_units, units_produced)

    money_in = sales_total + income_total
    money_out = operating_expenses
    net_cash_flow = money_in - money_out

    return {
        "month": f"{start:%Y-%m}",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "profit_and_loss": {
            "sales": sales_total,
            "other_income": income_total,
            "revenue": revenue_total,
            "cost_of_goods_sold": cost_of_goods,
            "gross_profit": gross_profit,
            "variable_costs": variable_costs,
            "operating_expenses": operating_expenses,
            "labor_cost": labor_cost,
            "fixed_costs": fixed_costs,
            "net_profit": net_profit,
            "labor_included": labor_cost is not None,
        },
        "ratios": {
            "gross_margin_pct": gross_margin,
            "labor_cost_ratio_pct": labor_ratio,
            "units_produced": units_produced,
            "units_sold": units_sold,
            "waste_units": waste_units,
            "waste_pct": waste_pct,
        },
        "cash_flow": {
            "money_in": money_in,
            "sales": sales_total,
            "income": income_total,
            "money_out": money_out,
            "net_cash_flow": net_cash_flow,
        },
    }


def render(report: dict, currency: str) -> None:
    M = lambda v: rc.money(v, currency)

    rc.header("MONTHLY REPORT",
              f"Month: {report['month']}  ({report['period']['start']} → {report['period']['end']})")

    pl = report["profit_and_loss"]
    rc.section("1. Profit & Loss")
    rc.kv("Sales", M(pl["sales"]))
    rc.kv("+ Other income", M(pl["other_income"]))
    rc.kv("= Revenue", M(pl["revenue"]))
    print()
    rc.kv("- Cost of goods sold", M(pl["cost_of_goods_sold"]))
    rc.kv("= Gross profit", M(pl["gross_profit"]))
    print()
    rc.kv("Variable costs (COGS)", M(pl["variable_costs"]))
    rc.kv("Operating expenses", M(pl["operating_expenses"]))
    rc.kv("Labour cost", M(pl["labor_cost"]) if pl["labor_included"] else "n/a (pass --labor-cost)")
    rc.kv("= Fixed costs", M(pl["fixed_costs"]))
    print()
    label = "= Net profit" if pl["labor_included"] else "= Net profit (before labour)"
    rc.kv(label, rc.signed_money(pl["net_profit"], currency))

    r = report["ratios"]
    rc.section("2. Key financial ratios")
    rc.kv("Gross margin", rc.percent(r["gross_margin_pct"]))
    rc.kv("Labour cost ratio", rc.percent(r["labor_cost_ratio_pct"]))
    rc.kv("Units produced", rc.qty(r["units_produced"]))
    rc.kv("Units sold", rc.qty(r["units_sold"]))
    rc.kv("Waste (produced - sold)", f"{rc.qty(r['waste_units'])} units  ({rc.percent(r['waste_pct'])})")

    cf = report["cash_flow"]
    rc.section("3. Cash flow")
    rc.kv("Money in (sales + income)", M(cf["money_in"]))
    rc.kv("Money out (expenses)", M(cf["money_out"]))
    rc.kv("Net cash flow", rc.signed_money(cf["net_cash_flow"], currency))
    print()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser("Monthly financial report for Adminator.")
    p.add_argument("--month", help="Month to report (YYYY-MM). Default: month of the latest day with sales.")
    p.add_argument("--labor-cost", type=str, default=None,
                   help="Labour cost for the month (else env ADMINATOR_LABOR_COST_MONTHLY).")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    if args.month:
        start, end = rc.parse_month(args.month)
    else:
        all_sales = store.sales()
        if not all_sales:
            sys.exit("No sales found in the system.")
        latest = max(rc.sale_date(s) for s in all_sales)
        start, end = rc.month_bounds(latest.year, latest.month)

    labor_cost = rc.resolve_optional(args.labor_cost, "ADMINATOR_LABOR_COST_MONTHLY")
    report = build_report(store, start, end, labor_cost)

    if args.json:
        rc.emit(report)
    else:
        render(report, args.currency)
    return 0


if __name__ == "__main__":
    sys.exit(main())
