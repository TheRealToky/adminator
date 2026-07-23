#!/usr/bin/env python3
r"""Export every processed material's recipe (bill of materials) to Excel.

Processed materials are the semi-finished goods — a dough, a sourdough starter,
a syrup — produced in their own batches and then drawn *from stock* by the
products that use them. This is the same export as ``product_recipes.py``, one
level down the bill of materials: one row per ingredient, with the processed
material it belongs to repeated on each row.

Batch quantities vs per-unit quantities
---------------------------------------
A processed material's recipe is written **per batch** ("40 kg of flour makes
one batch"), while its cost and the products that consume it work in **output
units**. Both are exported: ``Qty per batch`` is what the recipe says, and
``Qty per output unit`` divides it by ``Yield per batch`` — the same conversion
the app uses to cost a batch.

Sub-recipes
-----------
A processed material may itself contain another processed material. By default
such a line is listed as the sub-material it is; pass ``--expand-sub`` to
replace it with the raw materials behind it instead (resolved all the way
down), with the "Via" column naming the sub it came through.

Sheet 2, "Used in products"
---------------------------
The reverse view: one row per product that consumes each material, with what
the material contributes to that product's unit cost. A material used by
nothing is listed too, marked ``(not used in any product)`` — those are the
ones still being made for no one.

Costs
-----
``Line cost / batch`` is ``qty per batch × ingredient unit cost``, and ``Share``
is that line's slice of the batch's total ingredient cost. That total is
*ingredients only*: the material's own ``Unit cost`` is higher than
``batch cost ÷ yield`` because the app adds the material's overhead percentage
on top (the ``Overhead %`` column).

Inactive (discontinued) materials are excluded unless you ask for them. A
material with no recipe at all still gets a row, marked ``(no recipe)``, so a
missing bill of materials is visible rather than silently absent.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/reports/processed_material_recipes.py
    python scripts/reports/processed_material_recipes.py -o doughs.xlsx
    python scripts/reports/processed_material_recipes.py --expand-sub
    python scripts/reports/processed_material_recipes.py --include-inactive

Requirements (host): ``pip install openpyxl`` (already in requirements.txt).
"""
from __future__ import annotations

import argparse
import sys

import report_common as rc

# --expand-sub needs "raw materials per one output unit" for every processed
# material — sub-recipes resolved recursively, with a cycle guard.
# material_usage.py already does exactly that for its consumption maths, so the
# resolution lives there rather than being copied.
from material_usage import processed_raw_per_unit

DEFAULT_OUTPUT = "processed_material_recipes.xlsx"


# ── gathering ────────────────────────────────────────────────────────────────
def material_ingredients(material: dict, raw_by_id: dict, pm_by_id: dict,
                         pm_raw: dict | None) -> list[dict]:
    """Every ingredient line of one processed material, costliest first.

    Quantities stay per *batch* — :func:`build_materials` adds the per-output-
    unit figure once, from the same numbers. ``pm_raw`` is the expansion map
    ({material_id: {raw_id: qty per output unit}}); pass ``None`` to list a
    sub-recipe as the material it is.
    """
    rows = []
    for item in material.get("recipe_items", []):
        qty = rc.D(item["quantity"])

        if item.get("raw_material"):
            raw = raw_by_id.get(item["raw_material"], {})
            rows.append(rc.bom_line(
                rc.RAW,
                item.get("raw_material_name") or raw.get("name", "(unknown)"),
                raw.get("sku", ""),
                item.get("raw_material_unit") or raw.get("unit", ""),
                qty, raw.get("unit_cost"),
            ))
            continue

        sub_id = item.get("sub_processed_material")
        sub = pm_by_id.get(sub_id, {})
        if pm_raw is None:
            rows.append(rc.bom_line(
                rc.PROCESSED,
                item.get("sub_processed_material_name") or sub.get("name", "(unknown)"),
                sub.get("sku", ""),
                item.get("sub_processed_material_unit") or sub.get("unit", ""),
                qty, sub.get("unit_cost"),
            ))
            continue
        # Expanded: this much of the sub carries this much of each raw material.
        for raw_id, per_unit in pm_raw.get(sub_id, {}).items():
            raw = raw_by_id.get(raw_id, {})
            rows.append(rc.bom_line(
                rc.RAW, raw.get("name", "(unknown)"), raw.get("sku", ""),
                raw.get("unit", ""), qty * per_unit, raw.get("unit_cost"),
                via=sub.get("name", "(unknown)"),
            ))

    return rc.costliest_first(rows)


def build_materials(store: rc.DataStore, include_inactive: bool = True,
                    expand: bool = False) -> list[dict]:
    """``[{material fields…, "ingredients": [...], "batch_cost": Decimal}]``.

    Inactive materials are kept by default: a product recipe can still name one,
    and dropping it would leave that line unexplained. The standalone export
    passes ``include_inactive=False`` unless asked otherwise.
    """
    materials = store.processed_materials()
    if not include_inactive:
        materials = [m for m in materials if m.get("is_active", True)]

    raw_by_id = {m["id"]: m for m in store.raw_materials()}
    pm_by_id = {m["id"]: m for m in store.processed_materials()}
    pm_raw = processed_raw_per_unit(store.processed_materials()) if expand else None

    out = []
    for m in sorted(materials, key=lambda m: m["name"].lower()):
        # A zero or missing yield would make the per-output-unit column a
        # division by zero; the app requires a positive yield, so 1 is only
        # ever a fallback for a malformed row.
        per_batch = rc.D(m.get("yield_per_batch")) or rc.Decimal("1")
        rows = material_ingredients(m, raw_by_id, pm_by_id, pm_raw)
        for row in rows:
            row["per_output_unit"] = row["quantity"] / per_batch
        out.append({
            "id": m["id"],
            "sku": m.get("sku", ""),
            "name": m["name"],
            "unit": m.get("unit", ""),
            "is_active": m.get("is_active", True),
            "yield_per_batch": per_batch,
            "overhead_pct": rc.D(m.get("overhead_pct")),
            "unit_cost": rc.D(m.get("unit_cost")),
            "used_in": list(m.get("used_in_products", [])),
            "ingredients": rows,
            "batch_cost": sum((r["line_cost"] for r in rows), rc.ZERO),
        })
    return out


# ── sheet 1: the recipes ─────────────────────────────────────────────────────
def material_columns(currency: str) -> list[tuple]:
    """Column spec for the one-row-per-ingredient recipe sheet."""
    return [
        ("Material SKU", 14, None),
        ("Processed material", 30, None),
        ("Unit", 8, None),
        ("Yield per batch", 13, rc.QTY_FMT),
        ("Overhead %", 10, "0.##"),
        (f"Unit cost ({currency})", 13, rc.MONEY_FMT),
        ("Ingredient type", 16, None),
        ("Ingredient SKU", 14, None),
        ("Ingredient", 30, None),
        ("Via", 22, None),
        ("Ingredient unit", 10, None),
        ("Qty per batch", 13, rc.QTY_FMT),
        ("Qty per output unit", 15, rc.QTY_FMT),
        (f"Unit cost ({currency})", 13, rc.MONEY_FMT),
        (f"Line cost / batch ({currency})", 15, rc.MONEY_FMT),
        ("Share of batch cost", 12, rc.PCT_FMT),
    ]


def material_rows(materials: list[dict]) -> list[list]:
    rows = []
    for m in materials:
        head = [m["sku"], m["name"], m["unit"], m["yield_per_batch"],
                m["overhead_pct"], m["unit_cost"]]
        if not m["ingredients"]:
            rows.append(head + ["(no recipe)", "", "", "", "", None, None, None, None, None])
            continue
        for r in m["ingredients"]:
            rows.append(head + [
                r["kind"], r["sku"], r["name"], r["via"], r["unit"],
                r["quantity"], r["per_output_unit"], r["unit_cost"], r["line_cost"],
                rc.safe_div(r["line_cost"], m["batch_cost"]),
            ])
    return rows


# ── sheet 2: where each material goes ────────────────────────────────────────
def usage_columns(currency: str) -> list[tuple]:
    return [
        ("Material SKU", 14, None),
        ("Processed material", 30, None),
        ("Unit", 8, None),
        (f"Unit cost ({currency})", 13, rc.MONEY_FMT),
        ("Product SKU", 14, None),
        ("Product", 34, None),
        ("Category", 18, None),
        ("Qty per product unit", 16, rc.QTY_FMT),
        (f"Cost per product unit ({currency})", 16, rc.MONEY_FMT),
        (f"Product production cost ({currency})", 16, rc.MONEY_FMT),
        ("Share of production cost", 13, rc.PCT_FMT),
    ]


def usage_rows(materials: list[dict], products: list) -> list[list]:
    """One row per (material, product) pair, from the usages the materials
    endpoint already nests. ``Share of production cost`` is measured against the
    app's full production cost, overhead included — what the material is worth
    as a slice of the finished product, not of its ingredients alone.
    """
    by_id = {p["id"]: p for p in products}
    rows = []
    for m in materials:
        head = [m["sku"], m["name"], m["unit"], m["unit_cost"]]
        if not m["used_in"]:
            rows.append(head + ["", "(not used in any product)", "", None, None, None, None])
            continue
        usages = sorted(m["used_in"], key=lambda u: (u.get("product_name") or "").lower())
        for u in usages:
            product = by_id.get(u["product"], {})
            qty = rc.D(u["quantity"])
            cost = qty * m["unit_cost"]
            production_cost = rc.D(product.get("production_cost"))
            rows.append(head + [
                u.get("product_sku") or product.get("sku", ""),
                u.get("product_name") or product.get("name", "(unknown)"),
                product.get("category_name") or "",
                qty, cost, production_cost,
                rc.safe_div(cost, production_cost),
            ])
    return rows


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    rc.reconfigure_stdio()
    p = argparse.ArgumentParser(
        description="Export processed-material recipes (bills of materials) to an "
                    "Excel workbook, one row per ingredient.",
        epilog=rc.ENV_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base-url", default=rc.DEFAULT_BASE_URL)
    p.add_argument("--email", default=rc.DEFAULT_EMAIL)
    p.add_argument("--password", default=rc.DEFAULT_PASSWORD)
    p.add_argument("--currency", default=rc.CURRENCY,
                   help="Currency code shown in the money column headers.")
    p.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                   help=f"Path of the .xlsx file to write (default {DEFAULT_OUTPUT}).")
    p.add_argument("--expand-sub", action="store_true",
                   help="List the raw materials behind a sub-recipe instead of "
                        "the processed material itself.")
    p.add_argument("--include-inactive", action="store_true",
                   help="Also export discontinued (inactive) processed materials.")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    materials = build_materials(store, args.include_inactive, args.expand_sub)
    if not materials:
        sys.exit("No processed materials to export. Try --include-inactive.")

    wb = rc.xlsx_workbook()
    rc.xlsx_sheet(wb, "Processed recipes", material_columns(args.currency),
                  material_rows(materials), first=True)
    rc.xlsx_sheet(wb, "Used in products", usage_columns(args.currency),
                  usage_rows(materials, store.products()))
    wb.save(args.output)

    lines = sum(len(m["ingredients"]) for m in materials)
    unused = [m["name"] for m in materials if not m["used_in"]]
    empty = [m["name"] for m in materials if not m["ingredients"]]
    print(f"Wrote {args.output}")
    print(f"  {rc.num(len(materials))} processed materials, {rc.num(lines)} ingredient rows"
          + (" (sub-recipes expanded to raw)" if args.expand_sub else ""))
    print(f"  {rc.num(sum(len(m['used_in']) for m in materials))} product usages on sheet 2")
    for label, names in (("have no recipe", empty), ("are used in no product", unused)):
        if names:
            shown = ", ".join(names[:5]) + (" …" if len(names) > 5 else "")
            print(f"  ! {rc.num(len(names))} material(s) {label}: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
