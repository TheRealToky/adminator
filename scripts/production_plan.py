#!/usr/bin/env python3
r"""Recommend how many of each product to bake, from recent sales.

Answers "given what we sold, how much should we produce?" for a pastry shop
that bakes fresh each day. It reads the sales in a window (default this week,
2026-07-20 to 2026-07-23), works out demand per trading day for every product,
and turns that into a **produce-up-to** quantity per product.

Method — average + service level
--------------------------------
For each product we build its daily-demand series over the *open* days in the
window (a day the shop traded but sold none of that product counts as a 0 — a
real data point, not a gap). From that series:

    average  = mean units sold per open day
    sigma    = day-to-day standard deviation of that demand
    target   = average + z(service_level) * sigma        ("produce-up-to" level)

``z`` is the standard-normal quantile for the chosen service level, so the
target is the amount that, if demand is roughly normal, covers a day's sales on
about ``service_level`` of days. At the default 80% that is ``average + 0.84σ``:
a modest safety buffer over the mean so you sell out only about one day in five.
Turn the knob with ``--service-level`` (0.5 = just bake the average; 0.95 = rarely
run out, more likely to have leftovers). A steady seller (small sigma) gets a
target close to its average; a spiky one (big sigma) gets a bigger cushion.

From target to a bake list
--------------------------
    to bake = ceil( target * --horizon  −  finished units already on hand )

Targets are rounded **up** to whole units (you can't bake half a croissant) and
never go below zero. ``--horizon`` (default 1) scales a single day's target to a
multi-day bake. Current finished-goods stock is netted out so you don't rebake
what's already on the shelf; pass ``--ignore-stock`` to plan gross.

Caveats worth knowing
---------------------
* The default window is four days (Mon–Thu), so sigma rests on a small sample
  and there are **no weekend days** in it — treat the numbers as a starting
  point, not gospel, and widen ``--start``/``--end`` when you have more history.
* Demand is assumed roughly normal and independent day to day; that is a
  planning convenience, not a law. The plain **Avg/day** column is shown next to
  the target so you can always see the buffer the service level added.

Read-only by default. ``--commit`` schedules the plan as **planned** production
runs (``POST /production/runs/execute/`` with ``status=planned``) — a schedule
only, it consumes no raw materials. Add ``--execute`` to instead record them as
**completed** runs, which *does* draw down ingredients and add finished stock.

Usage
-----
    # this week's plan, one day's bake, to the terminal (no writes):
    python scripts/reports/production_plan.py

    # cover 90% of days, plan three days at once:
    python scripts/reports/production_plan.py --service-level 0.90 --horizon 3

    # a different window, machine-readable:
    python scripts/reports/production_plan.py --start 2026-07-06 --end 2026-07-19 --json

    # just the croissants, and don't net out what's on hand:
    python scripts/reports/production_plan.py --product croissant --ignore-stock

    # schedule the plan as planned runs for 2026-07-26 (dry-run first!):
    python scripts/reports/production_plan.py --scheduled-for 2026-07-26
    python scripts/reports/production_plan.py --scheduled-for 2026-07-26 --commit

Requirements (host): none beyond the standard library (report_common only uses
urllib); ``--docx`` additionally needs python-docx.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from datetime import timedelta

import report_common as rc

# The window the question was asked about; override with --start / --end.
DEFAULT_START = "2026-07-20"
DEFAULT_END = "2026-07-23"
DEFAULT_SERVICE_LEVEL = 0.80


# ── statistics helpers ───────────────────────────────────────────────────────
def inv_norm_cdf(p: float) -> float:
    """Standard-normal quantile Φ⁻¹(p) via Acklam's rational approximation.

    Kept dependency-free (no scipy) to match report_common's stdlib-only client.
    Accurate to ~1e-9 over (0, 1); the tails are clamped so a caller that passes
    an extreme service level gets a large-but-finite z rather than infinity.
    """
    if p <= 0.0:
        return -1e9
    if p >= 1.0:
        return 1e9
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def resolve_service_level(raw: float) -> float:
    """Accept 0.80 or 80 (percent); clamp to a sane (0.01, 0.999) band."""
    sl = float(raw)
    if sl > 1:
        sl /= 100.0
    return min(max(sl, 0.01), 0.999)


# ── product selection (SKU exact, else name substring) ───────────────────────
def resolve_products(products: list[dict], queries: list[str]) -> set[str]:
    """Return the ids of catalogue rows matching each query, case-insensitively."""
    matched: set[str] = set()
    for raw in queries:
        needle = raw.strip().lower()
        if not needle:
            continue
        hits = [p for p in products if (p.get("sku") or "").lower() == needle]
        if not hits:
            hits = [p for p in products if needle in (p.get("name") or "").lower()]
        if not hits:
            known = ", ".join(sorted(p.get("name", "") for p in products)[:15])
            sys.exit(f"No product matches {raw!r}. Known products include: {known} ...")
        matched.update(p["id"] for p in hits)
    return matched


# ── the plan ─────────────────────────────────────────────────────────────────
def build_plan(store, start, end, service_level, horizon, ignore_stock,
               wanted_ids, all_products):
    """Compute a per-product produce-up-to level and net bake quantity."""
    window = rc.sales_between(store.sales(), start, end)
    open_days = sorted({rc.sale_date(s) for s in window})
    if not open_days:
        sys.exit(f"No sales between {start} and {end} — nothing to plan from.")

    products = {p["id"]: p for p in store.products()}

    # Finished-goods on hand, so we can plan net of what's already baked.
    on_hand: dict[str, float] = {}
    if not ignore_stock:
        for row in store.api.get_all("/inventory/stock/?kind=product"):
            pid = row.get("product")
            if pid:
                on_hand[pid] = float(rc.D(row["quantity"]))

    # Per product: units sold on each open day (missing day = 0 sold).
    per_day: dict[str, dict] = {}
    names: dict[str, dict] = {}
    for sale in window:
        d = rc.sale_date(sale)
        for it in sale["items"]:
            pid = it["product"]
            if wanted_ids is not None and pid not in wanted_ids:
                continue
            names.setdefault(pid, {"name": it["product_name"], "sku": it.get("product_sku", "")})
            day_map = per_day.setdefault(pid, {})
            day_map[d] = day_map.get(d, 0.0) + float(rc.D(it["quantity"]))

    # Optionally seed products that never sold in the window (target 0) so an
    # explicit --product / --all-products request still lists them.
    if all_products or wanted_ids is not None:
        pool = wanted_ids if wanted_ids is not None else set(products)
        for pid in pool:
            if pid in per_day:
                continue
            p = products.get(pid)
            if not p or (not all_products and wanted_ids is None):
                continue
            if wanted_ids is None and not p.get("is_active", True):
                continue
            names.setdefault(pid, {"name": p.get("name", "(unknown)"), "sku": p.get("sku", "")})
            per_day[pid] = {}

    z = inv_norm_cdf(service_level)
    n_days = len(open_days)

    rows = []
    for pid, day_map in per_day.items():
        series = [day_map.get(d, 0.0) for d in open_days]      # length = open days
        total = sum(series)
        avg = statistics.mean(series) if series else 0.0
        sigma = statistics.stdev(series) if len(series) > 1 else 0.0
        target = max(0.0, avg + z * sigma)                     # produce-up-to / day
        stock = on_hand.get(pid, 0.0)
        to_bake = max(0, math.ceil(target * horizon - stock))

        cat = products.get(pid, {})
        prod_cost = rc.D(cat.get("production_cost"))
        sell_price = rc.D(cat.get("selling_price"))
        rows.append({
            "product_id": pid,
            "name": names.get(pid, {}).get("name", "(unknown)"),
            "sku": names.get(pid, {}).get("sku", ""),
            "unit": cat.get("unit", "unit"),
            "units_sold": total,
            "days_sold": sum(1 for v in series if v > 0),
            "avg_per_day": avg,
            "sigma_per_day": sigma,
            "target_per_day": target,
            "bake_per_day": math.ceil(target),
            "on_hand": stock,
            "to_bake": to_bake,
            "est_cost": prod_cost * to_bake,
            "est_revenue": sell_price * to_bake,
        })

    rows.sort(key=lambda r: (-r["target_per_day"], r["name"]))

    total_to_bake = sum(r["to_bake"] for r in rows)
    total_cost = sum((r["est_cost"] for r in rows), rc.ZERO)
    total_rev = sum((r["est_revenue"] for r in rows), rc.ZERO)

    return {
        "window": {
            "start": start, "end": end,
            "open_days": n_days, "receipts": len(window),
        },
        "method": {
            "name": "average + service level",
            "service_level": service_level,
            "z": z,
            "horizon_days": horizon,
            "net_of_stock": not ignore_stock,
        },
        "products": rows,
        "totals": {
            "products": len(rows),
            "units_to_bake": total_to_bake,
            "est_batch_cost": total_cost,
            "est_revenue_potential": total_rev,
        },
    }


# ── rendering ────────────────────────────────────────────────────────────────
def render(report, doc, currency, top):
    M = lambda v: rc.money(v, currency)
    w, m, t = report["window"], report["method"], report["totals"]
    sl_pct = f"{m['service_level'] * 100:.0f}%"

    doc.header(
        "PRODUCTION PLAN",
        f"Demand from {w['start'].isoformat()} to {w['end'].isoformat()}  "
        f"({w['open_days']} trading days, {rc.num(w['receipts'])} receipts)",
    )

    doc.section("Method")
    doc.kv("Rule", f"produce-up-to = average/day + z·σ/day")
    doc.kv("Service level", f"{sl_pct}  (z = {rc.num(m['z'], 2)})")
    doc.kv("Horizon", f"{rc.num(m['horizon_days'])} day(s) of bake")
    doc.kv("Net of on-hand stock", "yes" if m["net_of_stock"] else "no (gross plan)")

    horizon = m["horizon_days"]
    bake_hdr = "To bake" + (f" (×{rc.num(horizon)}d)" if horizon != 1 else "")
    doc.section("Bake list")
    if horizon != 1:
        doc.text(f"  'Bake/day' is one day's target; '{bake_hdr.strip()}' is the "
                 f"{rc.num(horizon)}-day quantity, net of stock.")
    rows = report["products"]
    shown = rows[:top] if top else rows
    doc.table(
        ["Product", "Sold", "Avg/day", "σ/day", f"Bake/day @{sl_pct}", "On hand", bake_hdr.strip()],
        [
            [r["name"], rc.qty(r["units_sold"]), rc.num(r["avg_per_day"], 1),
             rc.num(r["sigma_per_day"], 1), rc.num(r["bake_per_day"]),
             rc.qty(r["on_hand"]), rc.num(r["to_bake"])]
            for r in shown
        ],
        aligns=["l", "r", "r", "r", "r", "r", "r"],
    )
    if top and len(rows) > top:
        doc.text(f"  … {len(rows) - top} more product(s) (use --top 0 to show all)")

    doc.section("Totals")
    doc.kv("Products to bake", rc.num(sum(1 for r in rows if r["to_bake"] > 0)))
    doc.kv("Units to bake", rc.num(t["units_to_bake"]))
    doc.kv("Est. batch cost", M(t["est_batch_cost"]))
    doc.kv("Revenue potential", M(t["est_revenue_potential"]))
    doc.text()


# ── commit (schedule the plan as production runs) ────────────────────────────
def commit_plan(api, rows, scheduled_for, complete, window_label, log):
    """Create a run per product with something to bake. Planned unless --execute."""
    status = "completed" if complete else "planned"
    notes = f"Auto-plan (avg+service level) from sales {window_label}"
    created, failed = [], []
    for r in rows:
        if r["to_bake"] <= 0:
            continue
        try:
            _, data = api._request(
                "POST", "/production/runs/execute/",
                {"product": r["product_id"], "quantity": str(r["to_bake"]),
                 "scheduled_for": scheduled_for, "status": status, "notes": notes},
            )
            created.append((r, data))
            log(f"  ✓ {r['name']:<28} ×{r['to_bake']}  ({status}, run {str(data['id'])[:8]})")
        except rc.ApiError as exc:
            failed.append((r, exc))
            log(f"  ✗ {r['name']:<28} ×{r['to_bake']}  — {exc}")
    return created, failed


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser(
        "Recommend how many of each product to bake, from recent sales "
        "(average + service-level method)."
    )
    p.add_argument("--start", default=DEFAULT_START,
                   help=f"First day of the demand window (YYYY-MM-DD, default {DEFAULT_START}).")
    p.add_argument("--end", default=DEFAULT_END,
                   help=f"Last day of the demand window (YYYY-MM-DD, default {DEFAULT_END}).")
    p.add_argument("--service-level", type=float, default=DEFAULT_SERVICE_LEVEL,
                   help="Share of days the bake should cover, 0–1 (or a percent). "
                        f"Default {DEFAULT_SERVICE_LEVEL}. 0.5 = bake the average.")
    p.add_argument("--horizon", type=int, default=1,
                   help="Days of production to plan in one go (default 1).")
    p.add_argument("--product", default=None,
                   help="Only these products: SKU or name substring, comma-separated.")
    p.add_argument("--all-products", action="store_true",
                   help="Include active products that didn't sell in the window (target 0).")
    p.add_argument("--ignore-stock", action="store_true",
                   help="Plan gross — don't net out finished units already on hand.")
    p.add_argument("--top", type=int, default=0,
                   help="Show only the top N products by target (0 = all, the default).")
    p.add_argument("--scheduled-for", default=None,
                   help="Business date to schedule runs for (YYYY-MM-DD). "
                        "Default: the day after the window ends.")
    p.add_argument("--commit", action="store_true",
                   help="Actually create the runs (default: dry-run preview).")
    p.add_argument("--execute", action="store_true",
                   help="With --commit, record COMPLETED runs (consumes ingredients, "
                        "adds stock) instead of planned ones.")
    args = p.parse_args()

    start = rc.parse_date(args.start)
    end = rc.parse_date(args.end)
    if start > end:
        sys.exit(f"--start ({start}) is after --end ({end}).")
    if args.horizon < 1:
        sys.exit("--horizon must be at least 1.")
    service_level = resolve_service_level(args.service_level)

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    wanted_ids = None
    if args.product:
        queries = [q for q in args.product.split(",") if q.strip()]
        wanted_ids = resolve_products(store.products(), queries)

    report = build_plan(store, start, end, service_level, args.horizon,
                        args.ignore_stock, wanted_ids, args.all_products)

    if args.json:
        rc.emit(report)
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        render(report, doc, args.currency, args.top)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        render(report, rc.TerminalDoc(), args.currency, args.top)

    # ── optional write: schedule the plan ────────────────────────────────────
    scheduled_for = args.scheduled_for or (end + timedelta(days=1)).isoformat()
    to_make = [r for r in report["products"] if r["to_bake"] > 0]
    if not to_make:
        return 0

    kind = "COMPLETED (consumes ingredients)" if args.execute else "planned (schedule only)"
    if not args.json and not args.docx:
        print(rc.rule("─"))
        if args.commit:
            print(f"Scheduling {len(to_make)} run(s) as {kind} for {scheduled_for} …")
            created, failed = commit_plan(
                api, to_make, scheduled_for, args.execute,
                f"{start.isoformat()}..{end.isoformat()}", log=print,
            )
            print(f"\n  runs created : {len(created)}")
            print(f"  runs failed  : {len(failed)}")
            return 1 if failed else 0
        else:
            print(f"DRY-RUN — nothing written. {len(to_make)} run(s) would be created "
                  f"as {kind}\n  for {scheduled_for}. Re-run with --commit to schedule them "
                  f"(add --execute to record completed runs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
