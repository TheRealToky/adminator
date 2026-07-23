#!/usr/bin/env python3
r"""Reconcile raw-material stock to a physical count from an Excel file.

Reads a raw-materials export and, for every row, brings the app's on-hand
quantity in line with the sheet's ``In stock`` column by posting a manual
stock adjustment (``POST /inventory/stock/adjust/``).

The API takes a **signed delta**, not an absolute quantity, so for each row the
script reads the current on-hand figure and posts::

    delta = counted (sheet)  -  current (app)

A positive delta lands as ``adjustment_in``, a negative one as
``adjustment_out``. Rows already matching the app are a no-op (no write, no
movement row). Nothing here books a P&L expense — a shortfall is treated as a
*count correction*, not as waste. If you want the shortfall charged to the
books instead, that's ``/inventory/stock/write-off/`` and a different script.

Sheet layout (first row is a header, matched case-insensitively; column order
does not matter; extra columns such as Unit / Unit cost are ignored):

    SKU        | Name          | ... | In stock
    RM-AC-AC   | A/C           |     | 0
    RM-AL-PD   | Almond powder |     | 2.5

Matching
--------
Rows are matched by **SKU** first (exact, after trimming and upper-casing),
falling back to an exact case/accent-insensitive **Name** match when the SKU
cell is blank. Anything that can't be resolved confidently — or a name hitting
more than one material — is reported and skipped rather than guessed.

Blank ``In stock`` cells
------------------------
Controlled by ``--blank``:

* ``zero`` (default) — a blank cell means "none left"; the material is driven
  to 0. On a partially-filled sheet this will zero out every uncounted row, so
  **read the dry-run summary before committing**.
* ``skip`` — a blank cell means "not counted"; the material is left alone.

The dry-run prints how many rows each policy would touch, so you can compare
``--blank zero`` against ``--blank skip`` before writing anything.

Safe by default: runs in **dry-run** mode (planned deltas only, no writes).
Pass ``--commit`` to actually apply them.

Usage
-----
    # preview (no writes):
    python scripts/apply_stock_count.py --file "C:\path\raw-materials-20260718-1129.xlsx"

    # compare the other blank policy:
    python scripts/apply_stock_count.py --file "...xlsx" --blank skip

    # actually apply:
    python scripts/apply_stock_count.py --file "...xlsx" --commit

Requirements (host): ``pip install openpyxl`` (only extra dependency; HTTP uses
the standard library).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

try:
    import openpyxl
except ModuleNotFoundError:
    sys.exit('openpyxl is not installed.\n  Fix: python -m pip install openpyxl')

# ── defaults (override on the CLI or via env) ────────────────────────────────
DEFAULT_BASE_URL = os.environ.get("ADMINATOR_API", "http://localhost:8001/api/v1")
DEFAULT_EMAIL = os.environ.get("ADMINATOR_EMAIL", "admin@adminator.local")
DEFAULT_PASSWORD = os.environ.get("ADMINATOR_PASSWORD", "admin12345")
DEFAULT_FILE = os.environ.get("STOCK_COUNT_XLSX", "")

# Recognised header labels (normalized) -> logical column.
HEADER_ALIASES = {
    "sku": "sku",
    "name": "name",
    "raw material": "name",
    "material": "name",
    "in stock": "counted",
    "stock": "counted",
    "on hand": "counted",
    "quantity": "counted",
    "qty": "counted",
    "counted": "counted",
}

# StockItem.quantity is a DecimalField(max_digits=14, decimal_places=4)
FOUR_DP = Decimal("0.0001")


# ── small helpers ────────────────────────────────────────────────────────────
def normalize(name) -> str:
    """Lowercase, strip accents, collapse to space-separated alphanumeric tokens."""
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def parse_counted(raw):
    """Return a non-negative Decimal (4 dp), or raise ValueError with a reason.

    Raises ValueError("blank") for an empty cell so the caller can apply its
    own blank policy.
    """
    if raw is None or str(raw).strip() == "":
        raise ValueError("blank")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"not a number: {raw!r}")
    if value < 0:
        raise ValueError(f"negative: {value}")
    return value.quantize(FOUR_DP)


def fmt(qty: Decimal) -> str:
    """Trim trailing zeros so 2.5000 prints as 2.5 and 11.0000 as 11."""
    s = format(qty.normalize(), "f")
    return s


# ── API client (stdlib urllib; JWT bearer) ───────────────────────────────────
class ApiError(Exception):
    def __init__(self, status: int, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")

    @property
    def detail(self) -> str:
        if isinstance(self.body, dict):
            d = self.body.get("detail")
            if d:
                return str(d)
            return json.dumps(self.body)
        return str(self.body)


class Api:
    def __init__(self, base_url: str, email: str, password: str):
        self.base = base_url.rstrip("/")
        self.token: str | None = None
        _, data = self._request(
            "POST", "/auth/login/", {"email": email, "password": password}, auth=False
        )
        self.token = data["access"]

    def _request(self, method, path, payload=None, auth=True):
        url = self.base + path
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if auth and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = {"detail": raw[:300]}
            raise ApiError(exc.code, parsed)
        except urllib.error.URLError as exc:
            sys.exit(f"Could not reach {url}: {exc}. Is the scratch stack up?")

    def get_all(self, path: str) -> list:
        """Follow DRF pagination and return every result row."""
        sep = "&" if "?" in path else "?"
        _, data = self._request("GET", f"{path}{sep}page_size=1000")
        if isinstance(data, dict) and "results" in data:
            rows = list(data["results"])
            while data.get("next"):
                nxt = data["next"].split("/api/v1", 1)[-1]
                _, data = self._request("GET", nxt)
                rows.extend(data["results"])
            return rows
        return data or []

    def adjust_stock(self, raw_material_id, quantity_delta, reference, note):
        _, data = self._request(
            "POST", "/inventory/stock/adjust/",
            {
                "raw_material": raw_material_id,
                "quantity_delta": str(quantity_delta),
                "reference": reference,
                "note": note,
            },
        )
        return data


# ── material index / matching ────────────────────────────────────────────────
def index_materials(materials: list[dict]):
    """Build SKU and name lookups. Name maps to a *list* to flag duplicates."""
    by_sku: dict[str, dict] = {}
    by_name: dict[str, list[dict]] = {}
    for m in materials:
        by_sku[str(m["sku"]).strip().upper()] = m
        by_name.setdefault(normalize(m["name"]), []).append(m)
    return by_sku, by_name


def index_stock(stock_rows: list[dict]) -> dict[str, Decimal]:
    """Map raw_material id -> current on-hand quantity."""
    out: dict[str, Decimal] = {}
    for s in stock_rows:
        rm = s.get("raw_material")
        if rm:
            out[str(rm)] = Decimal(str(s["quantity"])).quantize(FOUR_DP)
    return out


def resolve(row, by_sku, by_name):
    """Return (material|None, reason). reason explains a None result."""
    sku = (row.get("sku") or "").strip().upper()
    if sku:
        m = by_sku.get(sku)
        if m:
            return m, "sku"
        return None, f"no raw material with SKU {sku!r}"
    name = row.get("name") or ""
    if not normalize(name):
        return None, "no SKU and no name"
    cands = by_name.get(normalize(name), [])
    if not cands:
        return None, f"no raw material named {name!r}"
    if len(cands) > 1:
        skus = ", ".join(sorted(c["sku"] for c in cands))
        return None, f"name {name!r} is ambiguous (SKUs: {skus}) — add a SKU"
    return cands[0], "name"


# ── spreadsheet ──────────────────────────────────────────────────────────────
def read_rows(path: str) -> list[dict]:
    """Read the sheet into dicts keyed by logical column (sku/name/counted)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header = next(rows_iter)
    except StopIteration:
        sys.exit(f"{path} is empty.")

    col_map: dict[int, str] = {}
    for idx, cell in enumerate(header):
        logical = HEADER_ALIASES.get(normalize(cell))
        if logical and logical not in col_map.values():
            col_map[idx] = logical
    if "counted" not in col_map.values():
        sys.exit(
            "Could not find an 'In stock' column in the header.\n"
            f"  Header seen: {[c for c in header]}"
        )

    out = []
    for i, r in enumerate(rows_iter, start=2):
        record = {"row": i, "sku": "", "name": "", "counted": None}
        for idx, logical in col_map.items():
            value = r[idx] if idx < len(r) else None
            if logical == "counted":
                record[logical] = value
            else:
                record[logical] = "" if value is None else str(value).strip()
        # skip fully-blank rows
        if not (record["sku"] or record["name"]) and record["counted"] in (None, ""):
            continue
        out.append(record)
    return out


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        description="Reconcile raw-material stock to a physical count from an Excel file."
    )
    p.add_argument("--file", default=DEFAULT_FILE, required=not DEFAULT_FILE,
                   help="Path to the raw-materials xlsx with an 'In stock' column")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--blank", choices=["zero", "skip"], default="zero",
                   help="How to treat a blank 'In stock' cell: drive to 0 (default) "
                        "or leave the material untouched.")
    p.add_argument("--reference", default="",
                   help="Movement reference (default: STOCKCOUNT-<yyyymmdd>).")
    p.add_argument("--commit", action="store_true",
                   help="Actually write (default: dry-run preview).")
    args = p.parse_args()

    reference = args.reference or f"STOCKCOUNT-{dt.date.today():%Y%m%d}"
    mode = "COMMIT" if args.commit else "DRY-RUN (no writes)"
    print(f"Stock count reconciliation · {mode}")
    print(f"File     : {args.file}")
    print(f"Target   : {args.base_url}")
    print(f"Blank    : {'treated as 0' if args.blank == 'zero' else 'skipped'}")
    print(f"Reference: {reference}\n")

    rows = read_rows(args.file)

    api = Api(args.base_url, args.email, args.password)
    materials = api.get_all("/catalog/raw-materials/")
    by_sku, by_name = index_materials(materials)
    current_by_id = index_stock(api.get_all("/inventory/stock/?kind=raw_material"))
    print(f"Loaded {len(materials)} raw materials, "
          f"{len(current_by_id)} with a stock row.\n")

    planned, unchanged, skipped, unmatched, bad_value = [], [], [], [], []
    blanks_zeroed = 0

    for r in rows:
        # validate the counted value first — a bad value is worth reporting even
        # if the material can't be matched.
        was_blank = False
        try:
            counted = parse_counted(r["counted"])
        except ValueError as exc:
            label = r["sku"] or r["name"] or f"row {r['row']}"
            if str(exc) == "blank":
                if args.blank == "skip":
                    skipped.append((r, "blank — not counted"))
                    continue
                counted = Decimal("0").quantize(FOUR_DP)
                was_blank = True
            else:
                bad_value.append((r, str(exc)))
                print(f"  ! BAD VALUE  {label:<24} — {exc} — skipped")
                continue

        material, reason = resolve(r, by_sku, by_name)
        if material is None:
            unmatched.append((r, reason))
            label = r["sku"] or r["name"] or f"row {r['row']}"
            print(f"  ? UNMATCHED  {label:<24} — {reason} — skipped")
            continue

        current = current_by_id.get(str(material["id"]), Decimal("0").quantize(FOUR_DP))
        delta = (counted - current).quantize(FOUR_DP)
        if delta == 0:
            unchanged.append((r, material))
            continue

        if was_blank:
            blanks_zeroed += 1
        arrow = "↑" if delta > 0 else "↓"
        flag = "  [blank→0]" if was_blank else ""
        print(f"  {arrow} {material['name']:<26} [{material['sku']:<10}] "
              f"{fmt(current)} → {fmt(counted)}  "
              f"(delta {'+' if delta > 0 else ''}{fmt(delta)}){flag}")
        planned.append((material, current, counted, delta, was_blank))

    done, failed = [], []
    if args.commit and planned:
        print("\nApplying…")
        for material, current, counted, delta, was_blank in planned:
            note = (
                f"Physical stock count {reference}: counted {fmt(counted)} "
                f"{material.get('unit', '')}".strip()
            )
            try:
                api.adjust_stock(material["id"], delta, reference, note)
                done.append((material, counted))
                print(f"  ✓ {material['name']} [{material['sku']}]  → {fmt(counted)}")
            except ApiError as exc:
                failed.append((material, exc))
                print(f"  ✗ {material['name']} [{material['sku']}]  — {exc.detail}")

    # ── summary ──
    increases = sum(1 for x in planned if x[3] > 0)
    decreases = sum(1 for x in planned if x[3] < 0)
    print("\n" + "=" * 60)
    print("Summary")
    print(f"  rows read            : {len(rows)}")
    print(f"  changes planned      : {len(planned)}  ({increases} up, {decreases} down)")
    if args.blank == "zero":
        print(f"    …of which blank→0  : {blanks_zeroed}")
    print(f"  already correct      : {len(unchanged)}")
    print(f"  skipped (blank)      : {len(skipped)}")
    print(f"  unmatched            : {len(unmatched)}"
          + (f"  → {', '.join((x[0]['sku'] or x[0]['name']) for x in unmatched)}" if unmatched else ""))
    print(f"  bad values           : {len(bad_value)}"
          + (f"  → {', '.join((x[0]['sku'] or x[0]['name']) for x in bad_value)}" if bad_value else ""))
    if args.commit:
        print(f"  applied              : {len(done)}")
        print(f"  failed               : {len(failed)}")
    else:
        if args.blank == "zero" and blanks_zeroed:
            print(f"\n  NOTE: {blanks_zeroed} of the {len(planned)} planned changes come from "
                  f"BLANK cells being\n        treated as 0. Re-run with --blank skip to see the "
                  f"count-only view.")
        print("\n  DRY-RUN — nothing written. Re-run with --commit to apply these changes.")
    return 1 if failed or bad_value or unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
