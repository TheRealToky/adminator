#!/usr/bin/env python3
r"""Average daily consumption of every raw material, from recorded production.

Answers "how much flour do we burn through on a normal day?" by replaying every
production event on record and attributing the raw materials it consumed to the
day it happened.

Where the numbers come from
---------------------------
The app never stores "raw material X was used on day D" directly — stock
movements are timestamped when they were *entered*, which for bulk-imported
history is the import date, not the baking date. So this script recomputes
consumption from the bills of materials instead, dated by each completed
production run's ``scheduled_for`` (the real day of work).

Every raw material is attributed to the **product run that needed it**, via a
fully expanded recipe. For one unit of a product that means:

* its **direct** recipe lines (``/catalog/products/`` → ``recipe_items``), plus
* the raw materials behind every **processed material** it uses — a Beef burger
  pulls in the flour and yeast of its burger bread, at ``usage.quantity ×
  the bread's raw-per-unit``. Processed materials nested inside other processed
  materials (Pizza dough ← Sourdough starter) are expanded all the way down.

Multiply that by ``run.quantity`` and the whole chain lands on the day the
product was made.

Processed-material **batches are deliberately ignored**. Counting a batch as
consumption *and* counting the same recipe again when the product is made would
double the raw materials; attributing at run time is the half that answers "what
does a day's output require". A consequence worth knowing: these figures are a
production-demand model, not a record of physical stock movement. Flour bought
and batched into dough on Monday for Tuesday's bread shows up on Tuesday, and a
batch made but never used in the window does not show up at all.

Pass ``--no-processed`` to count only the direct recipe lines, ignoring the
raw materials that reach a product through a processed material.

Averages
--------
**Days with no production at all are excluded from the denominator.** A closure
means nobody used flour, so counting those days would understate the real daily
draw. The headline ``Avg/production day`` — and the ``Cost/day`` and days-of-
cover figures derived from it — all divide by the number of days that actually
had a run or a batch.

Pass ``--include-idle-days`` to divide by every calendar day instead, which is
the right basis when you want "how much do we get through per week of the
calendar" for purchasing rather than "per day of baking".

A third, narrower figure sits alongside them: ``Avg/day used`` divides by the
days that *particular* material was touched. For something used on 3 days out of
26 that is far larger than either average above, and it is the number that says
how much to have on hand for a day that actually calls for it. The JSON carries
all three (``avg_per_active_day``, ``avg_per_calendar_day``, ``avg_per_day_used``)
whichever basis is selected.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/reports/material_usage.py                  # all history
    python scripts/reports/material_usage.py --days 30        # last 30 days
    python scripts/reports/material_usage.py --start 2026-06-01 --end 2026-06-30
    python scripts/reports/material_usage.py --top 15
    python scripts/reports/material_usage.py --flour          # flours only
    python scripts/reports/material_usage.py --include-idle-days   # calendar basis
    python scripts/reports/material_usage.py --material flour # day-by-day series
    python scripts/reports/material_usage.py --json
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

import report_common as rc

#: How ``--flour`` recognises a flour. The catalog gives the same six materials
#: under either rule today, so both are honoured: the SKU prefix keeps working if
#: a flour is named in French ("farine de manioc"), and the name match keeps
#: working if a new flour is filed under an off-pattern SKU.
FLOUR_SKU_PREFIX = "RM-FL"
FLOUR_NAME_WORDS = ("flour", "farine")


def is_flour(material: dict) -> bool:
    """True when a raw-material row looks like a flour."""
    if material.get("sku", "").upper().startswith(FLOUR_SKU_PREFIX):
        return True
    name = material.get("name", "").lower()
    return any(word in name for word in FLOUR_NAME_WORDS)


# ── bills of materials ───────────────────────────────────────────────────────
def product_raw_per_unit(products: list, pm_recipes: dict,
                         include_processed: bool = True) -> dict[str, dict[str, rc.Decimal]]:
    """``{product_id: {raw_material_id: qty per one product unit}}``.

    Two contributions per product, summed into one raw-material figure:

    * its **direct** recipe lines (flour straight into the dough), and
    * the raw materials behind each **processed material** it uses — a Beef
      burger's burger bread pulls in that bread's flour and yeast, at
      ``usage.quantity × pm_raw_per_unit``.

    ``pm_recipes`` comes from :func:`processed_raw_per_unit`, which has already
    divided by ``yield_per_batch`` and flattened any sub-recipes, so the second
    contribution is a plain multiply. With ``include_processed`` false only the
    direct lines count.
    """
    out: dict[str, dict[str, rc.Decimal]] = {}
    for p in products:
        recipe: dict[str, rc.Decimal] = {}
        for item in p.get("recipe_items", []):
            rm = item.get("raw_material")
            if rm:
                recipe[rm] = recipe.get(rm, rc.ZERO) + rc.D(item["quantity"])
        if include_processed:
            for usage in p.get("processed_usages", []):
                pm_id = usage.get("processed_material")
                if not pm_id:
                    continue
                per_product = rc.D(usage["quantity"])
                for rm, per_pm_unit in pm_recipes.get(pm_id, {}).items():
                    recipe[rm] = recipe.get(rm, rc.ZERO) + per_product * per_pm_unit
        out[p["id"]] = recipe
    return out


def processed_raw_per_unit(materials: list) -> dict[str, dict[str, rc.Decimal]]:
    """``{processed_material_id: {raw_material_id: qty per one output unit}}``.

    A processed material's recipe is expressed per *batch*, so the raw totals are
    divided by ``yield_per_batch``. Sub-recipes are resolved recursively: a
    sub-ingredient's quantity is in the sub's own units, so it multiplies that
    sub's already-per-unit raw requirements. The ``visiting`` set guards against
    a recipe cycle (the API rejects those, but a bad fixture shouldn't hang us).
    """
    by_id = {m["id"]: m for m in materials}
    resolved: dict[str, dict[str, rc.Decimal]] = {}

    def resolve(pm_id: str, visiting: frozenset) -> dict[str, rc.Decimal]:
        if pm_id in resolved:
            return resolved[pm_id]
        if pm_id in visiting or pm_id not in by_id:
            return {}
        pm = by_id[pm_id]
        per_batch: dict[str, rc.Decimal] = {}
        for item in pm.get("recipe_items", []):
            qty = rc.D(item["quantity"])
            if item.get("raw_material"):
                rm = item["raw_material"]
                per_batch[rm] = per_batch.get(rm, rc.ZERO) + qty
            elif item.get("sub_processed_material"):
                sub = resolve(item["sub_processed_material"], visiting | {pm_id})
                for rm, sub_qty in sub.items():
                    per_batch[rm] = per_batch.get(rm, rc.ZERO) + qty * sub_qty
        yield_per_batch = rc.D(pm.get("yield_per_batch")) or rc.Decimal("1")
        resolved[pm_id] = {rm: q / yield_per_batch for rm, q in per_batch.items()}
        return resolved[pm_id]

    for m in materials:
        resolve(m["id"], frozenset())
    return resolved


# ── event selection ──────────────────────────────────────────────────────────
def event_dates(runs: list) -> list[date]:
    """Every day that carries a completed product run.

    Processed-material batches are deliberately *not* events here. Their raw
    materials are attributed to the product runs that consume them, so a day
    holding only a batch carries no consumption — counting it as an active day
    would pad the denominator and dilute every average.
    """
    return [
        date.fromisoformat(r["scheduled_for"])
        for r in runs if r.get("status") == "completed"
    ]


#: An idle stretch at least this long is called out in the report. Shorter gaps
#: are just closing days and belong in the avg/day denominator; a stretch this
#: long is a closure, and silently dividing by it understates the daily draw.
IDLE_STRETCH_DAYS = 4


def idle_stretches(active: set, start: date, end: date, minimum: int = IDLE_STRETCH_DAYS):
    """Runs of ``minimum``+ consecutive days inside the window with no production.

    Returns ``[{"start", "end", "days"}]`` oldest first. A window that ends long
    after the last recorded run — asking for "the last 30 days" when the shop
    shut two weeks ago — shows up here as a trailing stretch.
    """
    out, run_start, day = [], None, start
    while day <= end:
        if day in active:
            if run_start is not None:
                length = (day - run_start).days
                if length >= minimum:
                    out.append({"start": run_start.isoformat(),
                                "end": (day - timedelta(days=1)).isoformat(),
                                "days": length})
                run_start = None
        elif run_start is None:
            run_start = day
        day += timedelta(days=1)
    if run_start is not None:
        length = (end - run_start).days + 1
        if length >= minimum:
            out.append({"start": run_start.isoformat(), "end": end.isoformat(),
                        "days": length})
    return out


def resolve_window(days: list[date], start_arg, end_arg, days_arg):
    """Pick the reporting window from the CLI flags, falling back to the data.

    With nothing specified the window spans the first to the last production day
    on record, so the average covers exactly the period we have data for.
    """
    end = rc.parse_date(end_arg) if end_arg else max(days)
    if days_arg:
        start = end - timedelta(days=days_arg - 1)
    elif start_arg:
        start = rc.parse_date(start_arg)
    else:
        start = min(days)
    return start, end


# ── core ─────────────────────────────────────────────────────────────────────
def consumption_by_day(runs, prod_recipes):
    """``{raw_material_id: {day: quantity consumed}}`` over the given runs.

    ``prod_recipes`` already folds each product's processed-material inputs into
    raw materials, so one pass over the product runs covers the whole chain.
    """
    usage: dict[str, dict[date, rc.Decimal]] = {}
    for r in runs:
        day = date.fromisoformat(r["scheduled_for"])
        made = rc.D(r["quantity"])
        for rm_id, per_unit in prod_recipes.get(r["product"], {}).items():
            qty = made * per_unit
            if qty <= 0:
                continue
            per_day = usage.setdefault(rm_id, {})
            per_day[day] = per_day.get(day, rc.ZERO) + qty
    return usage


def build_report(store: rc.DataStore, start_arg, end_arg, days_arg,
                 include_processed: bool, flour_only: bool = False,
                 basis: str = "active"):
    all_runs = store.runs()

    days = event_dates(all_runs)
    if not days:
        sys.exit("No completed production found in the system.")
    start, end = resolve_window(days, start_arg, end_arg, days_arg)

    runs = rc.completed_runs_between(all_runs, start, end)

    recipes = product_raw_per_unit(
        store.products(),
        processed_raw_per_unit(store.processed_materials()),
        include_processed,
    )
    usage = consumption_by_day(runs, recipes)

    calendar_days = (end - start).days + 1
    active = set(event_dates(runs))
    active_days = len(active)
    idle = idle_stretches(active, start, end)

    # The denominator behind every "per day" figure below — including cost/day
    # and days-of-cover, which have to move with it or the report contradicts
    # itself. Default is production days only: a closure means nobody used
    # flour, so counting those days would understate the daily draw.
    denominator = calendar_days if basis == "calendar" else active_days
    if not denominator:
        sys.exit(
            f"No production between {start} and {end}, so there is no daily "
            "average to compute. Widen the window with --start/--end."
        )

    materials = {m["id"]: m for m in store.raw_materials()}
    on_hand = {
        s["raw_material"]: rc.D(s["quantity"])
        for s in store.raw_material_stock() if s.get("raw_material")
    }

    rows = []
    for rm_id, per_day in usage.items():
        mat = materials.get(rm_id, {})
        total = sum(per_day.values(), rc.ZERO)
        avg = total / denominator
        stock = on_hand.get(rm_id)
        rows.append({
            "raw_material": rm_id,
            "name": mat.get("name", "(unknown)"),
            "sku": mat.get("sku", ""),
            "unit": mat.get("unit", ""),
            "unit_cost": rc.D(mat.get("unit_cost")),
            "total_used": total,
            "days_used": len(per_day),
            "avg_per_day": avg,
            # Both denominators are kept regardless of the chosen basis so a
            # JSON consumer can reconcile the headline figure without re-running.
            "avg_per_calendar_day": total / calendar_days,
            "avg_per_active_day": rc.safe_div(total, active_days),
            # Narrower still: the draw on the days this *particular* material was
            # touched. For an occasional material (used 3 days in 26) this is far
            # larger than the average above, and it is the number that says how
            # much to have on hand for a day that actually needs it.
            "avg_per_day_used": rc.safe_div(total, len(per_day)),
            "cost_per_day": avg * rc.D(mat.get("unit_cost")),
            "on_hand": stock,
            "days_of_cover": None if stock is None else rc.safe_div(stock, avg),
            "reorder_threshold": rc.D(mat.get("reorder_threshold")),
        })

    # Rank by what the material costs us per day: the top of that list is where
    # a change in yield or purchase price actually moves the P&L.
    rows.sort(key=lambda r: (-r["cost_per_day"], -r["avg_per_day"], r["name"]))

    # Filtering happens after the per-material figures are computed, so each row
    # keeps the same numbers it would have in the unfiltered report; only the
    # summary totals below are restated over the subset.
    if flour_only:
        rows = [r for r in rows if is_flour(r)]

    return {
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "calendar_days": calendar_days,
            "active_days": active_days,
            "production_runs": len(runs),
            "includes_processed_materials": include_processed,
            "filter": "flour" if flour_only else None,
            "idle_stretches": idle,
            "idle_days": sum(s["days"] for s in idle),
            "basis": basis,
            "denominator_days": denominator,
        },
        "materials": rows,
        "total_cost_per_day": sum((r["cost_per_day"] for r in rows), rc.ZERO),
    }


def material_series(store: rc.DataStore, report: dict, needle: str, include_processed: bool):
    """Day-by-day consumption for the one material matching ``needle``."""
    needle = needle.strip().lower()
    hits = [
        r for r in report["materials"]
        if needle in r["name"].lower() or needle == r["sku"].lower()
    ]
    if not hits:
        sys.exit(f"No consumed raw material matches {needle!r}.")
    if len(hits) > 1:
        exact = [r for r in hits if r["name"].lower() == needle]
        if not exact:
            names = ", ".join(r["name"] for r in hits[:10])
            sys.exit(f"{needle!r} matches several materials: {names}")
        hits = exact
    row = hits[0]

    start = rc.parse_date(report["window"]["start"])
    end = rc.parse_date(report["window"]["end"])
    usage = consumption_by_day(
        rc.completed_runs_between(store.runs(), start, end),
        product_raw_per_unit(
            store.products(),
            processed_raw_per_unit(store.processed_materials()),
            include_processed,
        ),
    ).get(row["raw_material"], {})

    day = start
    series = []
    while day <= end:
        series.append({"date": day.isoformat(), "quantity": usage.get(day, rc.ZERO)})
        day += timedelta(days=1)
    return {"material": row, "series": series, "basis": report["window"]["basis"]}


# ── rendering ────────────────────────────────────────────────────────────────
def render(report: dict, doc, currency: str, top: int) -> None:
    M = lambda v: rc.money(v, currency)
    w = report["window"]
    flour_only = w.get("filter") == "flour"
    noun = "flours" if flour_only else "materials"

    doc.header(
        "FLOUR — AVERAGE DAILY USE" if flour_only else "RAW MATERIAL — AVERAGE DAILY USE",
        f"{w['start']} to {w['end']}  ({w['calendar_days']} days, "
        f"{w['active_days']} with production)",
    )

    doc.section("Window")
    doc.kv("Production runs", rc.num(w["production_runs"]))
    doc.kv("Processed-material inputs",
           "included in product recipes" if w["includes_processed_materials"]
           else "excluded (--no-processed)")
    calendar_basis = w.get("basis") == "calendar"
    doc.kv("Calendar days", rc.num(w["calendar_days"]))
    doc.kv("Days with production", rc.num(w["active_days"]))
    doc.kv(
        "Averaging over",
        f"{rc.num(w['denominator_days'])} "
        + ("calendar days (--include-idle-days)" if calendar_basis
           else "production days (idle days excluded)"),
    )

    # Idle days are excluded by default, so this reads as an explanation of the
    # denominator rather than a caution — unless --include-idle-days put them
    # back in, in which case it is exactly the skew worth warning about.
    if w.get("idle_stretches"):
        idle_days = w["idle_days"]
        doc.text()
        doc.text(f"  {'!' if calendar_basis else '·'} {rc.num(idle_days)} of these "
                 f"{rc.num(w['calendar_days'])} days had no production at all:")
        for s in w["idle_stretches"]:
            span = s["start"] if s["days"] == 1 else f"{s['start']} to {s['end']}"
            doc.text(f"      {span}  ({rc.num(s['days'])} days)")
        if calendar_basis:
            doc.text("    They are in the denominator, which pulls every average")
            doc.text("    below down. Drop --include-idle-days to exclude them.")
        else:
            doc.text("    Excluded from the averages below.")

    rows = report["materials"]
    shown = rows[:top] if top else rows
    per = "calendar day" if calendar_basis else "production day"
    doc.section(f"Average consumption per {per}")
    doc.table(
        ["Material", "Unit", "Total used", "Days used", f"Avg/{per}", "Avg/day used", "Cost/day"],
        [
            [r["name"], r["unit"], rc.qty(r["total_used"], 3), rc.num(r["days_used"]),
             rc.qty(r["avg_per_day"], 3), rc.qty(r["avg_per_day_used"], 3),
             M(r["cost_per_day"])]
            for r in shown
        ],
        aligns=["l", "l", "r", "r", "r", "r", "r"],
    )
    doc.text('  "Avg/day used" divides by the days that material was actually'
             " touched, not every production day.")
    if top and len(rows) > top:
        doc.text(f"  … {len(rows) - top} more (use --top 0 to show all)")
    doc.text()
    doc.kv(f"{noun.capitalize()} consumed", rc.num(len(rows)))
    doc.kv(f"Total {noun[:-1]} cost/day", M(report["total_cost_per_day"]))

    cover = "Days of cover" if calendar_basis else "Production days of cover"
    doc.section("Stock cover at the current average")
    doc.text("  On-hand is the balance now, not as of the window end.")
    if not calendar_basis:
        doc.text("  Cover counts baking days, not calendar days — a closure buys"
                 " you extra calendar time.")
    doc.table(
        ["Material", "On hand", f"Avg/{per}", cover],
        [
            [r["name"],
             "n/a" if r["on_hand"] is None else rc.qty(r["on_hand"], 3),
             rc.qty(r["avg_per_day"], 3),
             "n/a" if r["days_of_cover"] is None else rc.qty(r["days_of_cover"], 1)]
            for r in shown
        ],
        aligns=["l", "r", "r", "r"],
    )
    doc.text()


def render_series(payload: dict, doc, currency: str) -> None:
    r = payload["material"]
    basis = payload.get("basis", "active")
    per = "calendar day" if basis == "calendar" else "production day"
    doc.header(
        f"DAILY USE — {r['name'].upper()}",
        f"{rc.qty(r['avg_per_day'], 3)} {r['unit']} per {per} "
        f"({rc.money(r['cost_per_day'], currency)}/day)",
    )
    doc.section("Day by day")
    doc.table(
        ["Date", f"Used ({r['unit']})"],
        [[d["date"], rc.qty(d["quantity"], 3)] for d in payload["series"]],
        aligns=["l", "r"],
    )
    doc.text()


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    rc.reconfigure_stdio()
    p = rc.base_arg_parser(
        "Average daily raw-material consumption, derived from recorded production."
    )
    p.add_argument("--start", help="First day of the window (YYYY-MM-DD). Default: first production day.")
    p.add_argument("--end", help="Last day of the window (YYYY-MM-DD). Default: last production day.")
    p.add_argument("--days", type=int, default=0,
                   help="Window length ending at --end (or the last production day).")
    p.add_argument("--top", type=int, default=25,
                   help="Show only the N costliest materials per day (0 = all).")
    p.add_argument("--material", default=None,
                   help="Show the day-by-day series for one material (name or SKU).")
    p.add_argument("--flour", action="store_true",
                   help="Only flours (SKU RM-FL*, or 'flour'/'farine' in the name).")
    p.add_argument("--include-idle-days", dest="basis", action="store_const",
                   const="calendar", default="active",
                   help="Divide by every calendar day in the window, including days "
                        "with no production (default: production days only).")
    p.add_argument("--no-processed", dest="processed", action="store_false",
                   help="Count only a product's direct recipe lines, ignoring raw "
                        "materials that reach it through a processed material.")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    report = build_report(store, args.start, args.end, args.days, args.processed,
                          flour_only=args.flour, basis=args.basis)
    if args.flour and not report["materials"]:
        sys.exit("No flour consumption found in this window.")
    if args.material:
        payload = material_series(store, report, args.material, args.processed)
        renderer = lambda doc: render_series(payload, doc, args.currency)
    else:
        payload = report
        renderer = lambda doc: render(report, doc, args.currency, args.top)

    if args.json:
        rc.emit(payload)
    elif args.docx:
        doc = rc.DocxDoc(args.currency)
        renderer(doc)
        doc.save(args.docx)
        print(f"Wrote {args.docx}")
    else:
        renderer(rc.TerminalDoc())
    return 0


if __name__ == "__main__":
    sys.exit(main())
