#!/usr/bin/env python3
r"""Order-volume report: how many orders the shop takes per day, by sale channel.

Answers "how many orders do we average per day?" over an arbitrary date window,
overall and split by the sale channel recorded on each receipt.

A note on "takeaway"
--------------------
The app has **no takeaway / dine-in flag**. The only order-type dimension a
receipt carries is ``Sale.channel``, whose choices are:

    counter    Counter / Walk-in
    online     Online order
    delivery   Delivery
    wholesale  Wholesale / B2B

So the closest stand-in for takeaway is the ``counter`` channel — but only if
the shop treats every walk-in as takeaway, which the data cannot confirm. The
channel table below lists *every* defined channel, including ones with zero
orders, so it is obvious which are actually in use before you read a number as
"takeaway".

Averaging and the denominator
-----------------------------
Two averages are reported, because they answer different questions:

* **per open day** — divided by the number of days in the window that recorded
  at least one sale *on any channel*. This is the trading average, and it is
  what you want when the window contains days the shop was shut.
* **per calendar day** — divided by every day in the window, closed days
  included. Lower whenever the shop didn't trade every day.

Open days are counted from all sales, not just the selected channels, so a
channel that sat idle on a trading day is correctly averaged over that day
rather than having it silently dropped from its denominator.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/reports/order_volume.py                     # full data span
    python scripts/reports/order_volume.py --start 2026-06-10 --end 2026-07-05
    python scripts/reports/order_volume.py --start 2026-06-10 --end 2026-07-05 --daily
    python scripts/reports/order_volume.py --channels counter --json
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


def known_channels(api) -> list[dict]:
    """The channel choices the backend defines, in declaration order.

    Fetched rather than hard-coded so a channel added to ``SaleChannel`` later
    shows up here (with zero orders) instead of silently vanishing.
    """
    try:
        rows = api.get_all("/sales/channels/")
    except rc.ApiError:
        return []
    return [r for r in rows if isinstance(r, dict) and "value" in r]


def build_report(store: rc.DataStore, start, end, channels: set[str] | None):
    all_in_window = rc.sales_between(store.sales(), start, end)

    # A day the shop traded — the denominator for the "per open day" averages.
    open_days = sorted({rc.sale_date(s) for s in all_in_window})
    calendar_days = list(day_range(start, end))

    selected = [
        s for s in all_in_window
        if channels is None or s.get("channel") in channels
    ]

    # Per-day order counts for the selected channels, zero-filled across the
    # whole window so the daily table and weekday averages both see closed days.
    per_day = {d: 0 for d in calendar_days}
    per_day_revenue = {d: rc.ZERO for d in calendar_days}
    for s in selected:
        d = rc.sale_date(s)
        per_day[d] += 1
        per_day_revenue[d] += rc.D(s["total"])

    orders = len(selected)
    revenue = rc.revenue(selected)

    # Channel breakdown. Every defined channel gets a row, including unused
    # ones — that absence is the point when you're looking for "takeaway".
    labels = {c["value"]: c["label"] for c in known_channels(store.api)}
    for s in all_in_window:  # fall back to whatever the rows themselves say
        labels.setdefault(s.get("channel", ""), s.get("channel_display") or s.get("channel", ""))

    by_channel: dict[str, dict] = {
        value: {"channel": value, "label": label, "orders": 0, "revenue": rc.ZERO}
        for value, label in labels.items()
    }
    for s in all_in_window:
        row = by_channel.setdefault(
            s.get("channel", ""),
            {"channel": s.get("channel", ""), "label": s.get("channel", ""),
             "orders": 0, "revenue": rc.ZERO},
        )
        row["orders"] += 1
        row["revenue"] += rc.D(s["total"])

    total_window_orders = len(all_in_window)
    channel_rows = []
    for row in by_channel.values():
        channel_rows.append({
            **row,
            "share_pct": rc.pct(row["orders"], total_window_orders),
            "per_open_day": rc.safe_div(row["orders"], len(open_days)),
            "avg_ticket": rc.safe_div(row["revenue"], row["orders"]),
            "selected": channels is None or row["channel"] in channels,
        })
    channel_rows.sort(key=lambda r: (-r["orders"], r["label"]))

    # Weekday profile: averaged over open days only, so a Sunday the shop was
    # shut doesn't drag the Sunday average toward zero.
    weekday_rows = []
    open_set = set(open_days)
    for idx, name in enumerate(WEEKDAYS):
        days = [d for d in open_days if d.weekday() == idx]
        counted = sum(per_day[d] for d in days)
        weekday_rows.append({
            "weekday": name,
            "open_days": len(days),
            "orders": counted,
            "avg_orders": rc.safe_div(counted, len(days)),
        })

    daily_rows = [
        {
            "date": d,
            "weekday": WEEKDAYS[d.weekday()],
            "orders": per_day[d],
            "revenue": per_day_revenue[d],
            "open": d in open_set,
        }
        for d in calendar_days
    ]

    busiest = max(daily_rows, key=lambda r: r["orders"]) if daily_rows else None
    quietest = min(
        (r for r in daily_rows if r["open"]), key=lambda r: r["orders"], default=None
    )

    return {
        "window": {
            "start": start,
            "end": end,
            "calendar_days": len(calendar_days),
            "open_days": len(open_days),
            "closed_days": [d for d in calendar_days if d not in open_set],
        },
        "channels_selected": sorted(channels) if channels else "all",
        "totals": {
            "orders": orders,
            "revenue": revenue,
            "avg_orders_per_open_day": rc.safe_div(orders, len(open_days)),
            "avg_orders_per_calendar_day": rc.safe_div(orders, len(calendar_days)),
            "avg_ticket": rc.safe_div(revenue, orders),
            "avg_revenue_per_open_day": rc.safe_div(revenue, len(open_days)),
            "busiest_day": None if busiest is None else
                {"date": busiest["date"], "orders": busiest["orders"]},
            "quietest_open_day": None if quietest is None else
                {"date": quietest["date"], "orders": quietest["orders"]},
        },
        "by_channel": channel_rows,
        "by_weekday": weekday_rows,
        "daily": daily_rows,
    }


def render(report: dict, doc, currency: str, show_daily: bool) -> None:
    M = lambda v: rc.money(v, currency)
    w = report["window"]
    sel = report["channels_selected"]

    doc.header(
        "ORDER VOLUME REPORT",
        f"{w['start'].isoformat()} to {w['end'].isoformat()}  "
        f"({w['calendar_days']} calendar days, {w['open_days']} with trading)",
    )

    t = report["totals"]
    doc.section("1. Averages")
    doc.kv("Channels counted", ", ".join(sel) if isinstance(sel, list) else "all channels")
    doc.kv("Orders in window", rc.num(t["orders"]))
    doc.kv("Avg orders / open day", rc.num(t["avg_orders_per_open_day"], 2))
    doc.kv("Avg orders / calendar day", rc.num(t["avg_orders_per_calendar_day"], 2))
    doc.text()
    doc.kv("Revenue", M(t["revenue"]))
    doc.kv("Avg revenue / open day", M(t["avg_revenue_per_open_day"]))
    doc.kv("Avg order value", M(t["avg_ticket"]) if t["avg_ticket"] is not None else "n/a")
    if t["busiest_day"]:
        b = t["busiest_day"]
        doc.kv("Busiest day", f"{b['date'].isoformat()}  ({rc.num(b['orders'])} orders)")
    if t["quietest_open_day"]:
        q = t["quietest_open_day"]
        doc.kv("Quietest open day", f"{q['date'].isoformat()}  ({rc.num(q['orders'])} orders)")
    if w["closed_days"]:
        doc.text()
        doc.text(f"  Days with no sales recorded ({len(w['closed_days'])}), excluded from "
                 "the per-open-day averages:")
        doc.text("    " + ", ".join(d.isoformat() for d in w["closed_days"]))

    doc.section("2. Orders by channel")
    doc.text("  Every channel the app defines, whether or not it was used.")
    doc.table(
        ["Channel", "Orders", "Share", "Per open day", "Revenue", "Avg ticket"],
        [
            [
                c["label"] + ("" if c["selected"] else "  (not counted above)"),
                rc.num(c["orders"]),
                rc.percent(c["share_pct"]),
                rc.num(c["per_open_day"], 2),
                M(c["revenue"]),
                M(c["avg_ticket"]) if c["avg_ticket"] is not None else "n/a",
            ]
            for c in report["by_channel"]
        ],
        aligns=["l", "r", "r", "r", "r", "r"],
    )

    doc.section("3. Orders by weekday")
    doc.text("  Averaged over open days only.")
    doc.table(
        ["Weekday", "Open days", "Orders", "Avg orders"],
        [
            [r["weekday"], rc.num(r["open_days"]), rc.num(r["orders"]),
             rc.num(r["avg_orders"], 2)]
            for r in report["by_weekday"]
        ],
        aligns=["l", "r", "r", "r"],
    )

    if show_daily:
        doc.section("4. Day by day")
        doc.table(
            ["Date", "Weekday", "Orders", "Revenue"],
            [
                [r["date"].isoformat(), r["weekday"], rc.num(r["orders"]),
                 M(r["revenue"]) if r["open"] else "(no sales)"]
                for r in report["daily"]
            ],
            aligns=["l", "l", "r", "r"],
        )
    doc.text()


def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser(
        "Average orders per day for Adminator, overall and by sale channel."
    )
    p.add_argument("--start", help="First day of the window (YYYY-MM-DD). "
                                   "Default: earliest recorded sale.")
    p.add_argument("--end", help="Last day of the window (YYYY-MM-DD). "
                                 "Default: latest recorded sale.")
    p.add_argument("--channels", default=None,
                   help="Comma-separated channels to average (e.g. 'counter' or "
                        "'counter,online'). Default: all channels.")
    p.add_argument("--daily", action="store_true",
                   help="Also print the day-by-day order counts.")
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

    channels = None
    if args.channels:
        channels = {c.strip() for c in args.channels.split(",") if c.strip()}
        valid = {c["value"] for c in known_channels(api)}
        unknown = channels - valid if valid else set()
        if unknown:
            sys.exit(
                f"Unknown channel(s): {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(sorted(valid))}."
            )

    report = build_report(store, start, end, channels)

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
