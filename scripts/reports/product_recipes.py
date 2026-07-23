#!/usr/bin/env python3
r"""Export every product's recipe (bill of materials) to an Excel workbook.

One row per ingredient, with the product it belongs to repeated on each row —
a flat table, so Excel's filter and pivot tools work on it directly.

What counts as an ingredient
----------------------------
A product's bill of materials has two halves, and both are exported:

* **Raw materials** — the product's own recipe lines (``recipe_items``), a
  quantity of flour/sugar/… per ONE unit of the product.
* **Processed materials** — semi-finished goods (a dough, a syrup) made in
  their own batches and drawn from stock. These are recorded separately, as a
  quantity of the processed material per ONE product unit.

By default a processed material is listed as the ingredient it is, which is how
the recipe actually reads on the workbench. Pass ``--expand-processed`` to
replace each such line with the raw materials behind it instead (sub-recipes
resolved all the way down); the "Via" column then names the processed material
each raw line came through. Note that an expanded line costs slightly *less*
than the processed line it replaced: a processed material's unit cost carries
its own overhead percentage, and expansion only counts ingredients.

The second sheet, "Processed materials", lists the processed-material recipes
themselves — one row per ingredient again — so a processed line on sheet one
can be looked up without expanding it. It is built by
``processed_material_recipes.py``, which exports the same thing standalone and
adds a "used in products" view.

Costs
-----
``Line cost`` is ``qty × ingredient unit cost``, and ``Share`` is that line's
slice of the product's total ingredient cost. That total is *ingredients only*:
the app's own ``Production cost`` column is higher because it adds the
product's overhead percentage on top.

Inactive (discontinued) products are excluded unless you ask for them. A
product with no recipe at all still gets a row, marked ``(no recipe)``, so a
missing bill of materials is visible rather than silently absent.

Read-only: this never writes to the backend.

Usage
-----
    python scripts/reports/product_recipes.py
    python scripts/reports/product_recipes.py -o recipes.xlsx
    python scripts/reports/product_recipes.py --expand-processed
    python scripts/reports/product_recipes.py --include-inactive

Requirements (host): ``pip install openpyxl`` (already in requirements.txt).
"""
from __future__ import annotations

import argparse
import sys

import report_common as rc

# --expand-processed needs "raw materials per one output unit" for every
# processed material — sub-recipes resolved recursively, with a cycle guard.
# material_usage.py already does exactly that for its consumption maths, so the
# resolution lives there rather than being copied.
from material_usage import processed_raw_per_unit

# Sheet two is the processed-material export in full, so it is built by that
# script rather than reimplemented here.
from processed_material_recipes import build_materials, material_columns, material_rows

DEFAULT_OUTPUT = "product_recipes.xlsx"


# ── gathering ────────────────────────────────────────────────────────────────
def usages_by_product(processed_materials: list) -> dict[str, list]:
    """``{product_id: [(processed_material, qty per product unit), …]}``.

    Built by inverting each processed material's ``used_in_products``, which the
    materials endpoint already nests — no extra request needed.
    """
    out: dict[str, list] = {}
    for pm in processed_materials:
        for usage in pm.get("used_in_products", []):
            out.setdefault(usage["product"], []).append((pm, rc.D(usage["quantity"])))
    return out


def product_ingredients(product: dict, raw_by_id: dict, usages: dict,
                        pm_raw: dict | None) -> list[dict]:
    """Every ingredient line of one product, costliest first.

    ``pm_raw`` is the expansion map ({processed_material_id: {raw_id: qty per
    output unit}}); pass ``None`` to list processed materials as themselves.
    """
    rows = []

    for item in product.get("recipe_items", []):
        raw = raw_by_id.get(item["raw_material"], {})
        rows.append(rc.bom_line(
            rc.RAW,
            item.get("raw_material_name") or raw.get("name", "(unknown)"),
            raw.get("sku", ""),
            item.get("raw_material_unit") or raw.get("unit", ""),
            item["quantity"],
            raw.get("unit_cost"),
        ))

    for pm, qty in usages.get(product["id"], []):
        if pm_raw is None:
            rows.append(rc.bom_line(
                rc.PROCESSED, pm["name"], pm.get("sku", ""), pm.get("unit", ""),
                qty, pm.get("unit_cost"),
            ))
            continue
        # Expanded: this much processed material carries this much of each raw.
        for raw_id, per_unit in pm_raw.get(pm["id"], {}).items():
            raw = raw_by_id.get(raw_id, {})
            rows.append(rc.bom_line(
                rc.RAW, raw.get("name", "(unknown)"), raw.get("sku", ""),
                raw.get("unit", ""), qty * per_unit, raw.get("unit_cost"),
                via=pm["name"],
            ))

    return rc.costliest_first(rows)


def build_products(store: rc.DataStore, include_inactive: bool, expand: bool) -> list[dict]:
    """``[{product fields…, "ingredients": [...], "recipe_cost": Decimal}]``."""
    products = store.products()
    if not include_inactive:
        products = [p for p in products if p.get("is_active", True)]

    raw_by_id = {m["id"]: m for m in store.raw_materials()}
    processed = store.processed_materials()
    usages = usages_by_product(processed)
    pm_raw = processed_raw_per_unit(processed) if expand else None

    out = []
    for p in sorted(products, key=lambda p: ((p.get("category_name") or "").lower(),
                                             p["name"].lower())):
        rows = product_ingredients(p, raw_by_id, usages, pm_raw)
        out.append({
            "id": p["id"],
            "sku": p.get("sku", ""),
            "name": p["name"],
            "category": p.get("category_name") or "",
            "unit": p.get("unit", ""),
            "is_active": p.get("is_active", True),
            "selling_price": rc.D(p.get("selling_price")),
            "production_cost": rc.D(p.get("production_cost")),
            "ingredients": rows,
            "recipe_cost": sum((r["line_cost"] for r in rows), rc.ZERO),
        })
    return out


# ── workbook ─────────────────────────────────────────────────────────────────
def product_sheet_rows(products: list[dict]) -> list[list]:
    rows = []
    for p in products:
        if not p["ingredients"]:
            rows.append([
                p["sku"], p["name"], p["category"], p["unit"],
                p["selling_price"], p["production_cost"],
                "(no recipe)", "", "", "", "", None, None, None, None,
            ])
            continue
        for r in p["ingredients"]:
            share = rc.safe_div(r["line_cost"], p["recipe_cost"])
            rows.append([
                p["sku"], p["name"], p["category"], p["unit"],
                p["selling_price"], p["production_cost"],
                r["kind"], r["sku"], r["name"], r["via"], r["unit"],
                r["quantity"], r["unit_cost"], r["line_cost"], share,
            ])
    return rows


def write_workbook(path: str, products: list[dict], processed: list[dict],
                   currency: str) -> None:
    columns = [
        ("Product SKU", 14, None),
        ("Product", 34, None),
        ("Category", 18, None),
        ("Product unit", 12, None),
        (f"Selling price ({currency})", 14, rc.MONEY_FMT),
        (f"Production cost ({currency})", 14, rc.MONEY_FMT),
        ("Ingredient type", 16, None),
        ("Ingredient SKU", 14, None),
        ("Ingredient", 34, None),
        ("Via", 22, None),
        ("Unit", 8, None),
        ("Qty per product unit", 16, rc.QTY_FMT),
        (f"Unit cost ({currency})", 13, rc.MONEY_FMT),
        (f"Line cost ({currency})", 13, rc.MONEY_FMT),
        ("Share of recipe cost", 12, rc.PCT_FMT),
    ]
    wb = rc.xlsx_workbook()
    rc.xlsx_sheet(wb, "Product recipes", columns, product_sheet_rows(products), first=True)
    if processed:
        rc.xlsx_sheet(wb, "Processed materials", material_columns(currency),
                      material_rows(processed))
    wb.save(path)


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    rc.reconfigure_stdio()
    p = argparse.ArgumentParser(
        description="Export product recipes (bills of materials) to an Excel workbook, "
                    "one row per ingredient.",
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
    p.add_argument("--expand-processed", action="store_true",
                   help="List the raw materials behind each processed material "
                        "instead of the processed material itself.")
    p.add_argument("--include-inactive", action="store_true",
                   help="Also export discontinued (inactive) products.")
    args = p.parse_args()

    api = rc.Api(args.base_url, args.email, args.password)
    store = rc.DataStore(api)

    products = build_products(store, args.include_inactive, args.expand_processed)
    if not products:
        sys.exit("No products to export. Try --include-inactive.")
    processed = build_materials(store)

    write_workbook(args.output, products, processed, args.currency)

    lines = sum(len(p["ingredients"]) for p in products)
    empty = [p["name"] for p in products if not p["ingredients"]]
    print(f"Wrote {args.output}")
    print(f"  {rc.num(len(products))} products, {rc.num(lines)} ingredient rows"
          + (" (processed materials expanded to raw)" if args.expand_processed else ""))
    if processed:
        pm_lines = sum(len(m["ingredients"]) for m in processed)
        print(f"  {rc.num(len(processed))} processed materials, "
              f"{rc.num(pm_lines)} ingredient rows on sheet 2")
    if empty:
        shown = ", ".join(empty[:5]) + (" …" if len(empty) > 5 else "")
        print(f"  ! {rc.num(len(empty))} product(s) have no recipe: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
