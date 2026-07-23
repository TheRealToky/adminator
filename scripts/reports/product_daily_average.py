#!/usr/bin/env python3
r"""Daily-average sales for one or more products.

Answers "how many of X do we sell on an average day?" over a date window, in
units and in money, plus how often X shows up on a receipt at all.

Written for the "Takeaway" product (the takeaway cup, SKU ``PR-TA-WY``), where
the attach rate is the interesting number: because a cup is added to an order
that is being taken away, the share of receipts containing one is a usable
proxy for "what fraction of our orders were takeaway". Note the app has no
takeaway flag on the sale itself (``Sale.channel`` only offers counter /
online / delivery / wholesale), so this proxy is as close as the data gets --
it undercounts any takeaway order where a cup wasn't rung up.

Averaging and the denominator
-----------------------------
Three denominators, because they answer different questions:

* **per open day** -- days in the window that recorded at least one sale of
  *anything*. The trading average, and the default one to quote.
* **per calendar day** -- every day in the window, closed days included.
* **per day sold** -- only days this product actually moved. Always the
  highest of the three; useful for spotting a product that sells in bursts,
  misleading as a headline figure.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/reports/product_daily_average.py --product Takeaway \
        --start 2026-06-10 --end 2026-07-05
    python scripts/reports/product_daily_average.py --product PR-TA-WY --daily
    python scripts/reports/product_daily_average.py --product Takeaway,Croissant
    python scripts/reports/product_daily_average.py          # every product, ranked
"""
from __future__ import annotations

import sys
from datetime import timedelta

import report_common as rc

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]


def day_range(start, end):
    """Every calendar day from ``start`` to ``end`` inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def resolve_products(products: list[dict], queries: list[str]) -> list[dict]:
    """Pick catalogue rows matching each query: exact SKU, else name substring.

    Matching is case-insensitive. A query that matches several products keeps
    them all (so ``--product cup`` reports every cup) rather than guessing.
    """
    matched: dict[str, dict] = {}
    for q in queries:
        needle = q.strip().lower()
        if not needle:
            continue
        hits = [p for p in products if (p.get("sku") or "").lower() == needle]
        if not hits:
            hits = [p for p in products if needle in (p.get("name") or "").lower()]
        if not hits:
            known = ", ".join(sorted(p.get("name", "") for p in products)[:15])
            sys.exit(f"No product matches {q!r}. Known products include: {known} ...")
        for p in hits:
            matched[p["id"]] = p
    return list(matched.values())


def build_report(store: rc.DataStore, start, end, selected: list[dict] | None):
    window = rc.sales_between(store.sales(), start, end)
    calendar_days = list(day_range(start, end))
    open_days = sorted({rc.sale_date(s) for s in window})
    open_count = len(open_days)
    total_receipts = len(window)

    # Roll up line items per product. rc.product_sales() gives units/revenue but
    # not receipt counts or a per-day series, both of which we need here.
    stats: dict[str, dict] = {}
    if selected is not None:
        for p in selected:  # seed so a product with zero sales still reports
            stats[p["id"]] = {
                "name": p.get("name", "(unknown)"), "sku": p.get("sku", ""),
                "units": rc.ZERO, "revenue": rc.ZERO, "cost": rc.ZERO,
                "receipts": 0, "per_day": {}, "per_day_revenue": {},
            }
    wanted = None if selected is None else {p["id"] for p in selected}

    for sale in window:
        d = rc.sale_date(sale)
        seen_in_this_receipt: set[str] = set()
        for item in sale["items"]:
            pid = item["product"]
            if wanted is not None and pid not in wanted:
                continue
            row = stats.setdefault(pid, {
                "name": item["product_name"], "sku": item.get("product_sku", ""),
                "units": rc.ZERO, "revenue": rc.ZERO, "cost": rc.ZERO,
                "receipts": 0, "per_day": {}, "per_day_revenue": {},
            })
            units = rc.D(item["quantity"])
            line = rc.D(item["line_total"])
            row["units"] += units
            row["revenue"] += line
            row["cost"] += rc.D(item["unit_cost"]) * units
            row["per_day"][d] = row["per_day"].get(d, rc.ZERO) + units
            row["per_day_revenue"][d] = row["per_day_revenue"].get(d, rc.ZERO) + line
            # One receipt containing the product counts once, however many
            # lines it was split across.
            if pid not in seen_in_this_receipt:
                row["receipts"] += 1
                seen_in_this_receipt.add(pid)

    rows = []
    for pid, row in stats.items():
        days_sold = len([d for d, u in row["per_day"].items() if u > 0])
        rows.append({
            "product_id": pid,
            "name": row["name"],
            "sku": row["sku"],
            "units": row["units"],
            "revenue": row["revenue"],
            "gross_profit": row["revenue"] - row["cost"],
            "receipts": row["receipts"],
            "days_sold": days_sold,
            "avg_units_per_open_day": rc.safe_div(row["units"], open_count),
            "avg_units_per_calendar_day": rc.safe_div(row["units"], len(calendar_days)),
            "avg_units_per_day_sold": rc.safe_div(row["units"], days_sold),
            "avg_revenue_per_open_day": rc.safe_div(row["revenue"], open_count),
            "avg_units_per_receipt_sold_on": rc.safe_div(row["units"], row["receipts"]),
            "attach_rate_pct": rc.pct(row["receipts"], total_receipts),
            "per_day": row["per_day"],
            "per_day_revenue": row["per_day_revenue"],
        })
    rows.sort(key=lambda r: (-r["units"], r["name"]))

    # Weekday profile only makes sense for a focused selection; build it for the
    # top row so the single-product case (the common one) gets it for free.
    weekday_rows = []
    if rows:
        top = rows[0]
        for idx, name in enumerate(WEEKDAYS):
            days = [d for d in open_days if d.weekday() == idx]
            units = sum((top["per_day"].get(d, rc.ZERO) for d in days), rc.ZERO)
            weekday_rows.append({
                "weekday": name,
                "open_days": len(days),
                "units": units,
                "avg_units": rc.safe_div(units, len(days)),
            })

    return {
        "window": {
            "start": start,
            "end": end,
            "calendar_days": len(calendar_days),
            "open_days": open_count,
            "closed_days": [d for d in calendar_days if d not in set(open_days)],
            "total_receipts": total_receipts,
        },
        "products": rows,
        "weekday_focus": None if not rows else rows[0]["name"],
        "by_weekday": weekday_rows,
        "daily": [
            {
                "date": d,
                "weekday": WEEKDAYS[d.weekday()],
                "units": rows[0]["per_day"].get(d, rc.ZERO) if rows else rc.ZERO,
                "revenue": rows[0]["per_day_revenue"].get(d, rc.ZERO) if rows else rc.ZERO,
                "open": d in set(open_days),
            }
            for d in calendar_days
        ],
    }


def render(report: dict, doc, currency: str, show_daily: bool, top: int) -> None:
    M = lambda v: rc.money(v, currency)
    w = report["window"]
    products = report["products"]

    doc.header(
        "PRODUCT DAILY AVERAGE",
        f"{w['start'].isoformat()} to {w['end'].isoformat()}  "
        f"({w['calendar_days']} calendar days, {w['open_days']} with trading, "
        f"{rc.num(w['total_receipts'])} receipts)",
    )

    if len(products) == 1:
        p = products[0]
        doc.section(f"1. {p['name']}" + (f"  ({p['sku']})" if p["sku"] else ""))
        doc.kv("Units sold", rc.qty(p["units"]))
        doc.kv("Avg units / open day", rc.num(p["avg_units_per_open_day"], 2))
        doc.kv("Avg units / calendar day", rc.num(p["avg_units_per_calendar_day"], 2))
        doc.kv("Avg units / day sold", rc.num(p["avg_units_per_day_sold"], 2))
        doc.kv("Days sold on", f"{rc.num(p['days_sold'])} of {rc.num(w['open_days'])} open days")
        doc.text()
        doc.kv("Revenue", M(p["revenue"]))
        doc.kv("Avg revenue / open day", M(p["avg_revenue_per_open_day"]))
        doc.kv("Gross profit", rc.signed_money(p["gross_profit"], currency))
        doc.text()
        doc.kv("Receipts containing it", rc.num(p["receipts"]))
        doc.kv("Attach rate", f"{rc.percent(p['attach_rate_pct'])} of all receipts")
        doc.kv("Avg units / such receipt", rc.num(p["avg_units_per_receipt_sold_on"], 2))
    else:
        doc.section("1. Products")
        shown = products[:top] if top else products
        doc.table(
            ["Product", "Units", "Avg/open day", "Days sold", "Receipts",
             "Attach %", "Revenue"],
            [
                [p["name"], rc.qty(p["units"]),
                 rc.num(p["avg_units_per_open_day"], 2), rc.num(p["days_sold"]),
                 rc.num(p["receipts"]), rc.percent(p["attach_rate_pct"]),
                 M(p["revenue"])]
                for p in shown
            ],
            aligns=["l", "r", "r", "r", "r", "r", "r"],
        )
        if top and len(products) > top:
            doc.text(f"  ... {len(products) - top} more (raise --top to show)")

    if w["closed_days"]:
        doc.text()
        doc.text(f"  Days with no sales at all ({len(w['closed_days'])}), excluded from "
                 "the per-open-day averages:")
        doc.text("    " + ", ".join(d.isoformat() for d in w["closed_days"]))

    if report["by_weekday"]:
        doc.section(f"2. {report['weekday_focus']} by weekday")
        doc.text("  Averaged over open days only.")
        doc.table(
            ["Weekday", "Open days", "Units", "Avg units"],
            [
                [r["weekday"], rc.num(r["open_days"]), rc.qty(r["units"]),
                 rc.num(r["avg_units"], 2)]
                for r in report["by_weekday"]
            ],
            aligns=["l", "r", "r", "r"],
        )

    if show_daily and products:
        doc.section(f"3. {report['weekday_focus']} day by day")
        doc.table(
            ["Date", "Weekday", "Units", "Revenue"],
            [
                [r["date"].isoformat(), r["weekday"], rc.qty(r["units"]),
                 M(r["revenue"]) if r["open"] else "(no sales)"]
                for r in report["daily"]
            ],
            aligns=["l", "l", "r", "r"],
        )
    doc.text()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser(
        "Daily-average unit and revenue sales for a product (or every product)."
    )
    p.add_argument("--product", default=None,
                   help="Product SKU or name substring; comma-separate for several. "
                        "Default: every product that sold in the window.")
    p.add_argument("--start", help="First day of the window (YYYY-MM-DD). "
                                   "Default: earliest recorded sale.")
    p.add_argument("--end", help="Last day of the window (YYYY-MM-DD). "
                                 "Default: latest recorded sale.")
    p.add_argument("--daily", action="store_true",
                   help="Also print the day-by-day series for the top product.")
    p.add_argument("--top", type=int, default=20,
                   help="Rows to show when listing every product (default 20; 0 = all).")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    sales = store.sales()
    if not sales:
        sys.exit("No sales found in the system.")
    start = rc.parse_date(args.start) if args.start else min(rc.sale_date(s) for s in sales)
    end = rc.parse_date(args.end) if args.end else max(rc.sale_date(s) for s in sales)
    if start > end:
        sys.exit(f"--start ({start}) is after --end ({end}).")

    selected = None
    if args.product:
        queries = [q for q in args.product.split(",") if q.strip()]
        selected = resolve_products(store.products(), queries)

    report = build_report(store, start, end, selected)

    if args.json:
        # The per-day maps are keyed by date objects; the daily list already
        # carries the same numbers in a JSON-friendly shape.
        payload = {
            **report,
            "products": [
                {k: v for k, v in p.items() if k not in ("per_day", "per_day_revenue")}
                for p in report["products"]
            ],
        }
        rc.emit(payload)
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        render(report, doc, args.currency, args.daily, args.top)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        render(report, rc.TerminalDoc(), args.currency, args.daily, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
