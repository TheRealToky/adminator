#!/usr/bin/env python3
r"""List every raw material with nothing on hand.

Read-only. Fetches the raw-material catalogue and the raw-material stock rows
(``GET /catalog/raw-materials/`` + ``GET /inventory/stock/?kind=raw_material``)
and reports every material whose on-hand quantity is 0.

Two things count as "0 on hand", and the report distinguishes them:

* ``0``  — the material has a stock row and it sits at zero.
* ``—``  — the material has **no stock row at all** (never received, never
  counted). The app treats this as zero too, but it usually means the material
  has simply never been stocked rather than having been run down.

Inactive materials are excluded by default (they're normally discontinued and
would only pad the list); pass ``--include-inactive`` to keep them.

Usage
-----
    # print the list:
    python scripts/list_zero_stock.py

    # include discontinued materials:
    python scripts/list_zero_stock.py --include-inactive

    # only those that are actually used in a product/recipe (the ones worth
    # reordering):
    python scripts/list_zero_stock.py --used-only

    # machine-readable, e.g. to paste into a purchase order:
    python scripts/list_zero_stock.py --csv > out-of-stock.csv

    # point at a different stack:
    python scripts/list_zero_stock.py --base-url http://localhost:8001/api/v1

Requirements (host): none beyond the standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal

# ── defaults (override on the CLI or via env) ────────────────────────────────
DEFAULT_BASE_URL = os.environ.get("ADMINATOR_API", "http://localhost:8001/api/v1")
DEFAULT_EMAIL = os.environ.get("ADMINATOR_EMAIL", "admin@adminator.local")
DEFAULT_PASSWORD = os.environ.get("ADMINATOR_PASSWORD", "admin12345")

# StockItem.quantity is a DecimalField(max_digits=14, decimal_places=4)
FOUR_DP = Decimal("0.0001")


# ── API client (stdlib urllib; JWT bearer) ───────────────────────────────────
class ApiError(Exception):
    def __init__(self, status: int, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


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
            sys.exit(f"Could not reach {url}: {exc}. Is the stack up?")

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


# ── helpers ──────────────────────────────────────────────────────────────────
def index_stock(stock_rows: list[dict]) -> dict[str, Decimal]:
    """Map raw_material id -> current on-hand quantity."""
    out: dict[str, Decimal] = {}
    for s in stock_rows:
        rm = s.get("raw_material")
        if rm:
            out[str(rm)] = Decimal(str(s["quantity"])).quantize(FOUR_DP)
    return out


def used_in(material: dict) -> int:
    """How many products / processed materials consume this raw material."""
    return (
        len(material.get("used_in_products") or [])
        + len(material.get("used_in_processed_materials") or [])
    )


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        description="List every raw material with 0 on hand."
    )
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--include-inactive", action="store_true",
                   help="Also report materials flagged inactive (default: skip).")
    p.add_argument("--used-only", action="store_true",
                   help="Only materials consumed by a product or processed material.")
    p.add_argument("--csv", action="store_true",
                   help="Emit CSV on stdout instead of the readable table.")
    args = p.parse_args()

    api = Api(args.base_url, args.email, args.password)
    materials = api.get_all("/catalog/raw-materials/")
    current_by_id = index_stock(api.get_all("/inventory/stock/?kind=raw_material"))

    zero, skipped_inactive, skipped_unused = [], 0, 0
    for m in materials:
        if not args.include_inactive and not m.get("is_active", True):
            continue
        qty = current_by_id.get(str(m["id"]))
        if qty is not None and qty != 0:
            continue
        if args.used_only and used_in(m) == 0:
            skipped_unused += 1
            continue
        if not m.get("is_active", True):
            skipped_inactive += 1
        zero.append((m, qty))

    zero.sort(key=lambda x: (str(x[0].get("name") or "")).lower())

    if args.csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["sku", "name", "unit", "on_hand", "has_stock_row",
                    "reorder_threshold", "used_in_count", "is_active"])
        for m, qty in zero:
            w.writerow([
                m.get("sku", ""), m.get("name", ""), m.get("unit", ""),
                "0" if qty is not None else "",
                "yes" if qty is not None else "no",
                m.get("reorder_threshold", ""),
                used_in(m),
                "yes" if m.get("is_active", True) else "no",
            ])
        return 0

    print(f"Raw materials with 0 on hand · {args.base_url}")
    print(f"Scanned {len(materials)} raw materials"
          + ("" if args.include_inactive else " (active only)") + "\n")

    if not zero:
        print("  Nothing out of stock. 🎉")
        return 0

    name_w = max(len(str(m.get("name") or "")) for m, _ in zero)
    name_w = min(max(name_w, 12), 40)
    print(f"  {'SKU':<12} {'NAME':<{name_w}} {'UNIT':<8} STOCK ROW")
    print(f"  {'-' * 12} {'-' * name_w} {'-' * 8} ---------")
    for m, qty in zero:
        name = str(m.get("name") or "")[:name_w]
        note = "0" if qty is not None else "— none (never stocked)"
        flag = "" if m.get("is_active", True) else "   [inactive]"
        print(f"  {str(m.get('sku') or ''):<12} {name:<{name_w}} "
              f"{str(m.get('unit') or ''):<8} {note}{flag}")

    at_zero = sum(1 for _, q in zero if q is not None)
    print("\n" + "=" * 60)
    print("Summary")
    print(f"  out of stock         : {len(zero)}")
    print(f"    …with a stock row  : {at_zero}")
    print(f"    …never stocked     : {len(zero) - at_zero}")
    if args.used_only:
        print(f"  hidden (unused)      : {skipped_unused}")
    if args.include_inactive:
        print(f"  of which inactive    : {skipped_inactive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
