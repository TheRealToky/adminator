#!/usr/bin/env python3
r"""Bulk-import multiple Excel files for sales, expenses, and/or production.

This is a thin orchestration layer on top of the three individual import
scripts (``import_sales.py``, ``import_expenses.py``, ``import_production.py``).
It accepts any number of files (or glob patterns) for each import type and
runs them in sequence, printing a consolidated summary at the end.

File type detection
-------------------
Each file is dispatched by its dedicated flag OR by filename heuristics:
  * ``*sales*``       -> sales import
  * ``*expense*``     -> expenses import
  * ``*production*``  -> production import

You can always be explicit with ``--sales-files``, ``--expense-files``,
and ``--production-files``.

Safe by default: **dry-run** (parse + match + plan, no writes). Pass
``--commit`` to write to the database.

Usage
-----
    # Dry-run preview for all three types at once:
    python scripts/bulk_import.py \
        --sales-files      "D:\data\sales\*.xlsx" \
        --expense-files    "D:\data\expenses\*.xlsx" \
        --production-files "D:\data\production\*.xlsx"

    # Commit only sales from two specific files:
    python scripts/bulk_import.py --commit \
        --sales-files "D:\data\sales_oct.xlsx" "D:\data\sales_nov.xlsx"

    # Auto-detect type from filename patterns:
    python scripts/bulk_import.py --commit \
        --files "D:\data\2026_10\*.xlsx"

Requirements: ``pip install openpyxl`` (HTTP uses standard library urllib).
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import sys
import json
import re
import datetime
import unicodedata
import urllib.error
import urllib.request
from collections import OrderedDict
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from difflib import SequenceMatcher

try:
    import openpyxl
except ModuleNotFoundError:
    sys.exit("openpyxl is not installed.\n  Fix: python -m pip install openpyxl")

# ── defaults (override on the CLI or via env) ────────────────────────────────
DEFAULT_BASE_URL = os.environ.get("ADMINATOR_API", "http://localhost:8001/api/v1")
DEFAULT_EMAIL = os.environ.get("ADMINATOR_EMAIL", "admin@adminator.local")
DEFAULT_PASSWORD = os.environ.get("ADMINATOR_PASSWORD", "admin12345")
DEFAULT_DATE = datetime.date.today().isoformat()
DEFAULT_OFFSET = "+02:00"          # Africa/Kigali (no DST)
DEFAULT_WALLET = "Petite caisse"
DEFAULT_CATEGORY = "Other"

# ── Sales constants (from import_sales.py) ───────────────────────────────────
SALES_SHEET_NAME = "Sales Lines"

PAYMENT_METHOD = {"momo": "mobile_money", "cash": "cash", "card": "card"}
SKIP_PAYMENT_METHODS = {"cevr"}
WALLET_FOR_METHOD = {
    "mobile_money": "Mobile money balance",
    "cash": "Petite caisse",
    "card": "Bank",
}

SALES_PRODUCT_ALIASES = {
    "baguette brown": "Brown baguette",
    "coffee latte": "Latte",
    "panini tuna": "Tuna panini",
    "salad chicken": "Chicken salad",
    "sourdhough bread promo": "Sourdough bread",
}

SALES_MATCH_THRESHOLD = 0.82
MAX_TOPUP_ROUNDS = 60
MAX_PRODUCE_ROUNDS = 40

INSUFFICIENT_RE = re.compile(
    r"Not enough stock of (.+?): have ([\d.]+), requested ([\d.]+)\."
)

# ── Production constants (from import_production.py) ─────────────────────────
PRODUCTION_SHEET_NAME = "Production"
COL_PRODUCT = 0
COL_PRODUCTION = 5
COL_NOTES = 6

PRODUCTION_PRODUCT_ALIASES = {
    "baguette au levain": "Sourdough baguette",
    "baguette traditionnelle": "Traditional Baguette",
    "pain au levain": "Sourdough bread",
    "pain complet": "Brown bread",
    "pain aux grains": "Baguette with seeds",
    "cinnamon rolls": "Cinnamon roll",
    "bon muffins": "Muffin",
    "mangue passion": "Tarte mangue passion",
    "tarte chocolat": "Tarte au chocolat",
    "moka cafe": "Mocha",
    "quiche au thon": "Quiche",
}

PRODUCTION_MATCH_THRESHOLD = 0.82

# ── Expense constants (from import_expenses.py) ──────────────────────────────
EXPENSES_SHEET_NAME = "Expenses"

SKIP_STATUSES = {"voided", "cancelled", "annule", "annule", "rejected", "deleted"}

PAYMENT_METHOD_MAP = {
    "cash": "cash",
    "espece": "cash",
    "especes": "cash",
    "petite caisse": "cash",
    "grosse caisse": "cash",
    "momo": "mobile_money",
    "mobile money": "mobile_money",
    "mobile_money": "mobile_money",
    "mtn": "mobile_money",
    "airtel": "mobile_money",
    "card": "card",
    "carte": "card",
    "pos": "card",
    "bank": "bank_transfer",
    "bank transfer": "bank_transfer",
    "bank_transfer": "bank_transfer",
    "virement": "bank_transfer",
    "transfer": "bank_transfer",
}

EXPENSE_WALLET_FOR_METHOD = {
    "cash": "Petite caisse",
    "mobile_money": "Mobile money balance",
    "card": "Bank",
    "bank_transfer": "Bank",
}

CATEGORY_ALIASES = {
    "electricity": "Utilities",
    "electricite": "Utilities",
    "cash power": "Utilities",
    "cashpower": "Utilities",
    "water": "Utilities",
    "eau": "Utilities",
    "wasac": "Utilities",
    "regideso": "Utilities",
    "internet": "Utilities",
    "wifi": "Utilities",
    "canalbox": "Utilities",
    "mtn internet": "Utilities",
    "airtime": "Utilities",
    "telephone": "Utilities",
    "gas": "Utilities",
    "gaz": "Utilities",
    "cleaning": "Cleaning supplies",
    "nettoyage": "Cleaning supplies",
    "savon": "Cleaning supplies",
    "soap": "Cleaning supplies",
    "detergent": "Cleaning supplies",
    "javel": "Cleaning supplies",
    "maintenance": "Maintenance",
    "reparation": "Maintenance",
    "repair": "Maintenance",
    "technicien": "Maintenance",
    "packaging": "Packaging",
    "emballage": "Packaging",
    "boxes": "Packaging",
    "boites": "Packaging",
    "sachets": "Packaging",
    "bags": "Packaging",
    "labels": "Packaging",
    "stickers": "Packaging",
    "transport": "Transport",
    "taxi": "Transport",
    "carburant": "Transport",
    "fuel": "Transport",
    "essence": "Transport",
    "diesel": "Transport",
    "livraison": "Transport",
    "delivery": "Transport",
    "moto": "Transport",
    "office": "Office supplies",
    "office supplies": "Office supplies",
    "bureau": "Office supplies",
    "papeterie": "Office supplies",
    "stationery": "Office supplies",
    "printer ink": "Office supplies",
    "papier": "Office supplies",
    "marketing": "Marketing",
    "ads": "Marketing",
    "publicite": "Marketing",
    "flyers": "Marketing",
    "salary": "Payroll",
    "salaries": "Payroll",
    "salaire": "Payroll",
    "salaires": "Payroll",
    "payroll": "Payroll",
    "advance": "Payroll",
    "avance": "Payroll",
    "rent": "Rent",
    "loyer": "Rent",
}

EXPENSE_MATCH_THRESHOLD = 0.75


# ── small helpers ─────────────────────────────────────────────────────────────
def normalize(name: str) -> str:
    """Lowercase, strip accents, reduce to space-separated alphanumeric tokens."""
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_insufficient(detail: str | None):
    if not detail:
        return None
    m = INSUFFICIENT_RE.search(detail)
    if not m:
        return None
    return m.group(1), Decimal(m.group(2)), Decimal(m.group(3))


def topup_amount(have: Decimal, requested: Decimal) -> Decimal:
    deficit = Decimal(requested) - Decimal(have)
    if deficit <= 0:
        deficit = Decimal("0.0001")
    return deficit.quantize(Decimal("0.0001"), rounding=ROUND_CEILING)


def to_iso(date_val, time_val, offset: str, fallback_date: str) -> str:
    """Build an ISO8601 timestamp with explicit offset from sheet Date + Time."""
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        d = date_val.strftime("%Y-%m-%d")
    elif date_val:
        d = str(date_val).strip()[:10]
    else:
        d = fallback_date
    if isinstance(time_val, (datetime.time, datetime.datetime)):
        t = time_val.strftime("%H:%M:%S")
    else:
        t = (str(time_val).strip() if time_val else "12:00")
        parts = t.split(":")
        if len(parts) == 2:
            t = f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
    return f"{d}T{t}{offset}"


def parse_date(date_val, fallback_date: str) -> str:
    """Extract standard YYYY-MM-DD date string."""
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        return date_val.strftime("%Y-%m-%d")
    if date_val is not None:
        s = str(date_val).strip()
        m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
        if m:
            return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return fallback_date


def parse_time(time_val) -> str | None:
    """Extract HH:MM:SS or HH:MM time string if present."""
    if isinstance(time_val, datetime.time):
        return time_val.strftime("%H:%M:%S")
    if isinstance(time_val, datetime.datetime):
        return time_val.strftime("%H:%M:%S")
    if time_val is not None:
        s = str(time_val).strip()
        if s:
            parts = s.split(":")
            if len(parts) >= 2:
                try:
                    h, m_part = int(parts[0]), int(parts[1])
                    return f"{h:02d}:{m_part:02d}:00"
                except ValueError:
                    pass
            return s
    return None


def parse_amount(val) -> Decimal:
    """Parse number or currency string into Decimal."""
    if val is None:
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return Decimal("0")
    s = str(val).strip()
    s = re.sub(r"[^\d.-]", "", s)
    if not s or s == "-" or s == ".":
        return Decimal("0")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def expand_globs(patterns: list[str]) -> list[str]:
    """Expand a list of file paths / glob patterns to actual existing files."""
    files = []
    for pat in patterns:
        matches = glob.glob(pat, recursive=True)
        if matches:
            files.extend(sorted(matches))
        elif os.path.isfile(pat):
            files.append(pat)
        else:
            print(f"  ! Warning: no files matched pattern: {pat!r}", file=sys.stderr)
    seen: set[str] = set()
    deduped = []
    for f in files:
        key = os.path.abspath(f)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


def detect_type(path: str) -> str | None:
    """Guess import type from filename; returns 'sales', 'expenses', or 'production'."""
    name = os.path.basename(path).lower()
    if "sales" in name:
        return "sales"
    if "expense" in name:
        return "expenses"
    if "production" in name or "prod" in name:
        return "production"
    return None


# ── API client ────────────────────────────────────────────────────────────────
class ApiError(Exception):
    def __init__(self, status: int, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")

    @property
    def detail(self) -> str:
        if isinstance(self.body, dict):
            d = self.body.get("detail")
            return str(d) if d else json.dumps(self.body)
        return str(self.body)


class Api:
    def __init__(self, base_url: str, email: str, password: str):
        self.base = base_url.rstrip("/")
        self.token: str | None = None
        _, data = self._request(
            "POST", "/auth/login/", {"email": email, "password": password}, auth=False
        )
        self.token = data["access"]

    def _request(self, method: str, path: str, payload=None, auth: bool = True):
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
            sys.exit(f"Could not reach {url}: {exc}. Is the backend API running?")

    def get_all(self, path: str) -> list[dict]:
        """Fetch all results following DRF pagination."""
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

    def record_sale(self, payload: dict) -> dict:
        _, data = self._request("POST", "/sales/sales/record/", payload)
        return data

    def execute_production(self, product_id, quantity, scheduled_for, notes=""):
        _, data = self._request(
            "POST", "/production/runs/execute/",
            {"product": product_id, "quantity": str(quantity),
             "scheduled_for": scheduled_for, "status": "completed", "notes": notes},
        )
        return data

    def receive_material(self, raw_material_id, quantity, note="", reference=""):
        _, data = self._request(
            "POST", "/inventory/stock/receive/",
            {"raw_material": raw_material_id, "quantity": str(quantity),
             "note": note, "reference": reference},
        )
        return data

    def create_transaction(self, payload: dict) -> dict:
        _, data = self._request("POST", "/finance/transactions/", payload)
        return data

    def create_transaction_category(self, name: str, direction: str = "expense", description: str = "") -> dict:
        _, data = self._request(
            "POST", "/finance/transaction-categories/",
            {"name": name, "direction": direction, "description": description, "is_active": True},
        )
        return data

    def create_expense(self, payload: dict) -> dict:
        _, data = self._request("POST", "/finance/expenses/", payload)
        return data

    def create_expense_category(self, name: str, description: str = "") -> dict:
        _, data = self._request(
            "POST", "/finance/expense-categories/",
            {"name": name, "description": description, "is_active": True},
        )
        return data


# ── name matching ─────────────────────────────────────────────────────────────
class ProductMatcher:
    """Resolve a sheet product name to a catalog product (sales + production)."""

    def __init__(self, products: list[dict], aliases: dict[str, str], threshold: float):
        self.products = products
        self.threshold = threshold
        self.by_norm: dict[str, dict] = {}
        for p in products:
            self.by_norm.setdefault(normalize(p["name"]), p)
        self.alias_norm: dict[str, dict] = {}
        for sheet_name, catalog_name in aliases.items():
            target = self.by_norm.get(normalize(catalog_name))
            if target is None:
                print(f"  ! alias target not in catalog: {catalog_name!r}", file=sys.stderr)
            else:
                self.alias_norm[normalize(sheet_name)] = target

    def match(self, name: str):
        """Return (product|None, method, score)."""
        n = normalize(name)
        if not n:
            return None, "empty", 0.0
        if n in self.alias_norm:
            return self.alias_norm[n], "alias", 1.0
        if n in self.by_norm:
            return self.by_norm[n], "exact", 1.0
        best, best_score = None, 0.0
        n_sorted = " ".join(sorted(n.split()))
        for p in self.products:
            pn = normalize(p["name"])
            score = max(
                SequenceMatcher(None, n, pn).ratio(),
                SequenceMatcher(None, n_sorted, " ".join(sorted(pn.split()))).ratio(),
            )
            if score > best_score:
                best, best_score = p, score
        if best_score >= self.threshold:
            return best, "fuzzy", best_score
        return None, "unmatched", best_score


class CategoryMatcher:
    """Matches an expense name / description to a Category."""

    def __init__(self, categories: list[dict], aliases: dict[str, str],
                 default_name: str = DEFAULT_CATEGORY):
        self.categories = categories
        self.by_norm: dict[str, dict] = {}
        for c in categories:
            self.by_norm[normalize(c["name"])] = c
        self.alias_norm: dict[str, dict] = {}
        for alias_key, cat_name in aliases.items():
            target = self.by_norm.get(normalize(cat_name))
            if target:
                self.alias_norm[normalize(alias_key)] = target
        self.default_category = (
            self.by_norm.get(normalize(default_name))
            or self.by_norm.get("other")
            or (categories[0] if categories else None)
        )

    def match(self, name: str) -> tuple[dict | None, str, float]:
        """Return (category, method, score)."""
        n = normalize(name)
        if not n:
            return self.default_category, "default_empty", 0.0
        if n in self.by_norm:
            return self.by_norm[n], "exact", 1.0
        if n in self.alias_norm:
            return self.alias_norm[n], "alias", 1.0
        for alias_key, target in self.alias_norm.items():
            if alias_key in n or n in alias_key:
                return target, "alias_sub", 0.90
        best, best_score = None, 0.0
        n_sorted = " ".join(sorted(n.split()))
        for c in self.categories:
            cn = normalize(c["name"])
            score = max(
                SequenceMatcher(None, n, cn).ratio(),
                SequenceMatcher(None, n_sorted, " ".join(sorted(cn.split()))).ratio(),
            )
            if score > best_score:
                best, best_score = c, score
        if best and best_score >= EXPENSE_MATCH_THRESHOLD:
            return best, "fuzzy", best_score
        if self.default_category:
            return self.default_category, "fallback", best_score
        return None, "unmatched", best_score


# ── shared catalog helpers ───────────────────────────────────────────────────
def index_materials(stock_rows: list[dict]) -> dict[str, list[dict]]:
    """Map normalized raw-material name -> [{id, name, stock}] for top-ups."""
    idx: dict[str, list[dict]] = {}
    for row in stock_rows:
        if row.get("kind") != "raw_material" or not row.get("raw_material"):
            continue
        entry = {"id": row["raw_material"], "name": row["item_name"],
                 "stock": Decimal(str(row["quantity"]))}
        idx.setdefault(normalize(row["item_name"]), []).append(entry)
    return idx


def resolve_material(materials: dict, name: str, have: Decimal):
    cands = materials.get(normalize(name), [])
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    for c in cands:
        if c["stock"] == have:
            return c
    return cands[0]


def resolve_wallet(
    wallets_by_name: dict[str, dict],
    payment_method: str,
    cash_wallet_name: str = DEFAULT_WALLET,
) -> dict | None:
    """Find the target wallet for an expense based on its payment method."""
    target_wallet_name = (
        cash_wallet_name if payment_method == "cash"
        else EXPENSE_WALLET_FOR_METHOD.get(payment_method, "Petite caisse")
    )
    if target_wallet_name in wallets_by_name:
        return wallets_by_name[target_wallet_name]
    norm_target = normalize(target_wallet_name)
    for name, w in wallets_by_name.items():
        if normalize(name) == norm_target:
            return w
    fallback_aliases = {
        "mobile_money": ["Mobile money balance", "MTN Mobile Money", "Mobile Money", "MoMo"],
        "card": ["Bank", "Bank of Kigali - current", "Card terminal float", "Bank Account"],
        "bank_transfer": ["Bank", "Bank of Kigali - current", "Bank Account"],
        "cash": [cash_wallet_name, "Petite caisse", "Petty cash", "Front-counter drawer", "Caisse"],
    }
    for alias in fallback_aliases.get(payment_method, []):
        norm_alias = normalize(alias)
        for name, w in wallets_by_name.items():
            if normalize(name) == norm_alias:
                return w
    target_type = (
        "mobile_money" if payment_method == "mobile_money"
        else ("cash" if payment_method == "cash" else "bank")
    )
    for w in wallets_by_name.values():
        if w.get("account_type") == target_type and w.get("is_active", True):
            return w
    return next(iter(wallets_by_name.values()), None) if wallets_by_name else None


# ── production helpers ────────────────────────────────────────────────────────
def produce_with_topup(api: Api, product: dict, quantity: Decimal, date: str,
                       materials: dict, log) -> dict:
    """Record a production run, topping up any short raw material and retrying."""
    notes = f"Imported from production sheet ({date})"
    last_short = None
    for _ in range(MAX_TOPUP_ROUNDS):
        try:
            return api.execute_production(product["id"], quantity, date, notes)
        except ApiError as exc:
            if exc.status != 400:
                raise
            info = parse_insufficient(exc.detail)
            if info is None:
                raise
            mat_name, have, requested = info
            mat = resolve_material(materials, mat_name, have)
            if mat is None:
                raise RuntimeError(
                    f"raw material {mat_name!r} (from error) not found in catalog"
                )
            amount = topup_amount(have, requested)
            api.receive_material(
                mat["id"], amount,
                note=f"Auto top-up so '{product['name']}' production can run (bulk import)",
                reference="BULK-IMPORT-PROD",
            )
            mat["stock"] = have + amount
            log(f"      up topped up {mat_name}: +{amount} (had {have}, needed {requested})")
            last_short = mat_name
    raise RuntimeError(
        f"gave up after {MAX_TOPUP_ROUNDS} top-up rounds (stuck on {last_short})"
    )


def record_sale_with_production(api: Api, payload: dict, matcher: ProductMatcher,
                                materials: dict, prod_date: str, log) -> dict:
    """Record a sale; bake any out-of-stock product on demand, then retry."""
    for _ in range(MAX_PRODUCE_ROUNDS):
        try:
            return api.record_sale(payload)
        except ApiError as exc:
            if exc.status != 400:
                raise
            info = parse_insufficient(exc.detail)
            if info is None:
                raise
            pname, have, requested = info
            product, _, _ = matcher.match(pname)
            if product is None:
                raise RuntimeError(f"out-of-stock product {pname!r} not in catalog")
            qty = Decimal(max(1, math.ceil(Decimal(requested) - Decimal(have))))
            log(f"      out of stock: {pname} (have {have}, need {requested}) -> producing {qty}")
            produce_with_topup(api, product, qty, prod_date, materials, log)
    raise RuntimeError("too many produce/retry passes for one sale")


# ── spreadsheet readers ───────────────────────────────────────────────────────
def read_sales_orders(path: str, fallback_date: str, offset: str):
    """Read the sales sheet into grouped orders.

    Returns (orders, voided, skipped_orders); mirrors import_sales.read_orders.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[SALES_SHEET_NAME] if SALES_SHEET_NAME in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    col = {name: i for i, name in enumerate(header)}

    def cell(r, name):
        i = col.get(name)
        return r[i] if i is not None and i < len(r) else None

    orders: "OrderedDict[tuple, dict]" = OrderedDict()
    voided = 0
    skipped_orders: dict = {}
    for r in rows[1:]:
        name = cell(r, "Product Name")
        order_id = cell(r, "Order Id")
        if name is None or order_id is None:
            continue
        if str(cell(r, "Status")).strip().lower() == "voided":
            voided += 1
            continue
        method_raw = str(cell(r, "Payment Method") or "").strip().lower()
        if method_raw in SKIP_PAYMENT_METHODS:
            skipped_orders[order_id] = method_raw.upper()
            continue
        method = PAYMENT_METHOD.get(method_raw)
        key = (order_id, method or method_raw)
        if key not in orders:
            orders[key] = {
                "order_id": order_id,
                "method_raw": method_raw,
                "method": method,
                "occurred_at": to_iso(cell(r, "Date"), cell(r, "Time"), offset, fallback_date),
                "lines": [],
            }
        orders[key]["lines"].append({
            "product_name": str(name).strip(),
            "qty": cell(r, "Qty"),
            "total": cell(r, "Total Price"),
        })
    for key in [k for k in orders if k[0] in skipped_orders]:
        del orders[key]
    return orders, voided, skipped_orders


def read_production_rows(path: str) -> list[dict]:
    """Read the production sheet; mirrors import_production.read_rows."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[PRODUCTION_SHEET_NAME] if PRODUCTION_SHEET_NAME in wb.sheetnames else wb.worksheets[0]
    rows = []
    for i, r in enumerate(ws.iter_rows(values_only=True), start=1):
        if i == 1:
            continue  # header
        name = r[COL_PRODUCT] if len(r) > COL_PRODUCT else None
        if name is None or str(name).strip() == "":
            continue
        qty = r[COL_PRODUCTION] if len(r) > COL_PRODUCTION else None
        note = r[COL_NOTES] if len(r) > COL_NOTES else None
        rows.append({"row": i, "name": str(name).strip(), "qty": qty, "note": note})
    return rows


def read_expense_rows(path: str, fallback_date: str) -> tuple[list[dict], int, int]:
    """Parse Excel workbook into structured expense rows.

    Returns (rows, skipped_voided_count, skipped_zero_count);
    mirrors import_expenses.read_expense_sheet.
    """
    if not os.path.exists(path):
        print(f"  ! File not found: {path}", file=sys.stderr)
        return [], 0, 0

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[EXPENSES_SHEET_NAME] if EXPENSES_SHEET_NAME in wb.sheetnames else wb.worksheets[0]
    raw_rows = list(ws.iter_rows(values_only=True))

    if not raw_rows:
        return [], 0, 0

    header = [str(h).strip() if h is not None else "" for h in raw_rows[0]]
    col_map = {normalize(name): i for i, name in enumerate(header) if name}

    def get_cell(row, *aliases):
        for alias in aliases:
            idx = col_map.get(normalize(alias))
            if idx is not None and idx < len(row):
                return row[idx]
        return None

    parsed_rows, skipped_voided, skipped_zero = [], 0, 0

    for i, r in enumerate(raw_rows[1:], start=2):
        if not any(r):
            continue
        exp_id = get_cell(r, "Expense ID", "Expense Id", "ID", "Ref", "Reference")
        name = get_cell(r, "Name", "Expense Name", "Title", "Description", "Item")
        amount_raw = get_cell(r, "Amount (RWF)", "Amount", "Total", "Total (RWF)")
        method_raw = get_cell(r, "Payment Method", "Payment_Method", "Method")
        time_raw = get_cell(r, "Time", "Heure")
        date_raw = get_cell(r, "Date", "Date Incurred")
        status_raw = get_cell(r, "Status", "Statut")
        notes_raw = get_cell(r, "Notes", "Note", "Comment", "Comments")

        if not name or str(name).strip() == "":
            continue

        name_clean = str(name).strip()
        status_clean = str(status_raw or "").strip().lower()

        if status_clean in SKIP_STATUSES:
            skipped_voided += 1
            continue

        amount = parse_amount(amount_raw)
        if amount <= Decimal("0"):
            skipped_zero += 1
            continue

        parsed_rows.append({
            "row_num": i,
            "expense_id": str(exp_id).strip() if exp_id is not None else "",
            "name": name_clean,
            "amount": amount,
            "payment_method_raw": str(method_raw or "").strip(),
            "time": parse_time(time_raw),
            "date": parse_date(date_raw, fallback_date),
            "status": status_clean,
            "notes": str(notes_raw).strip() if notes_raw is not None else "",
        })

    return parsed_rows, skipped_voided, skipped_zero


# ── per-file import runners ───────────────────────────────────────────────────

def import_sales_file(
    path: str,
    api: Api,
    products: list[dict],
    materials: dict,
    wallets: dict,
    date: str,
    offset: str,
    use_sheet_prices: bool,
    commit: bool,
    limit: int,
) -> dict:
    """Import one sales Excel file. Returns a result summary dict."""
    print(f"\n  -- Sales: {os.path.basename(path)}")
    matcher = ProductMatcher(products, SALES_PRODUCT_ALIASES, SALES_MATCH_THRESHOLD)

    try:
        orders, voided, skipped_orders = read_sales_orders(path, date, offset)
    except Exception as exc:
        print(f"    x Failed to read file: {exc}", file=sys.stderr)
        return {"file": path, "type": "sales", "error": str(exc)}

    for needed in WALLET_FOR_METHOD.values():
        if needed not in wallets:
            print(f"    x Required wallet {needed!r} not found -- skipping file.",
                  file=sys.stderr)
            return {"file": path, "type": "sales", "error": f"missing wallet {needed!r}"}

    sales, unmatched_lines, bad_orders = [], [], []
    by_method_total = {"mobile_money": Decimal("0"), "cash": Decimal("0"), "card": Decimal("0")}

    for (order_id, _), o in orders.items():
        if o["method"] is None:
            bad_orders.append((order_id, f"unknown payment method {o['method_raw']!r}"))
            continue
        items, line_descr = [], []
        order_total = Decimal("0")
        for ln in o["lines"]:
            product, method, score = matcher.match(ln["product_name"])
            if product is None:
                unmatched_lines.append((order_id, ln["product_name"], score))
                continue
            qty = Decimal(str(ln["qty"]))
            item = {"product": product["id"], "quantity": str(qty)}
            if use_sheet_prices:
                sheet_total = Decimal(str(ln["total"]))
                unit_price = (sheet_total / qty).quantize(Decimal("0.01")) if qty else Decimal("0")
                item["unit_price"] = str(unit_price)
            else:
                unit_price = Decimal(str(product["selling_price"]))
            items.append(item)
            order_total += (unit_price * qty).quantize(Decimal("0.01"))
            tag = method if method != "fuzzy" else f"~{score:.2f}"
            line_descr.append(f"{product['name']}x{qty}@{unit_price}[{tag}]")
        if not items:
            bad_orders.append((order_id, "no matchable items"))
            continue
        payload = {
            "items": items,
            "payment_method": o["method"],
            "channel": "counter",
            "occurred_at": o["occurred_at"],
            "wallet": wallets[WALLET_FOR_METHOD[o["method"]]],
            "notes": f"Imported from sales sheet -- order {order_id}",
        }
        sales.append({"order_id": order_id, "method": o["method"], "total": order_total,
                      "payload": payload, "descr": line_descr})
        by_method_total[o["method"]] += order_total
        print(f"    order {str(order_id):>3} [{o['method']:<12}] "
              f"{WALLET_FOR_METHOD[o['method']]:<20} {order_total:>8} : "
              + ", ".join(line_descr))

    if unmatched_lines:
        print("    Unmatched lines (skipped):")
        for oid, nm, sc in unmatched_lines:
            print(f"      order {oid}: {nm!r}  (best score {sc:.2f})")

    if limit:
        sales = sales[:limit]

    done, failed = [], []
    if commit and sales:
        print("    Recording sales...")
        for s in sales:
            try:
                sale = record_sale_with_production(
                    api, s["payload"], matcher, materials, date, log=print)
                done.append(sale)
                print(f"    + order {s['order_id']} [{s['method']}] {s['total']} "
                      f"-> {sale['receipt_number']} (total {sale['total']})")
            except (ApiError, RuntimeError) as exc:
                msg = exc.detail if isinstance(exc, ApiError) else str(exc)
                failed.append((s["order_id"], msg))
                print(f"    x order {s['order_id']} [{s['method']}] -- {msg}")

    return {
        "file": path,
        "type": "sales",
        "planned": len(sales),
        "voided": voided,
        "cevr_skipped": len(skipped_orders),
        "unmatched": len(unmatched_lines),
        "bad_orders": len(bad_orders),
        "totals": {k: float(v) for k, v in by_method_total.items()},
        "done": len(done),
        "failed": len(failed),
    }


def import_production_file(
    path: str,
    api: Api,
    products: list[dict],
    materials: dict,
    date: str,
    commit: bool,
    limit: int,
) -> dict:
    """Import one production Excel file. Returns a result summary dict."""
    print(f"\n  -- Production: {os.path.basename(path)}")
    matcher = ProductMatcher(products, PRODUCTION_PRODUCT_ALIASES, PRODUCTION_MATCH_THRESHOLD)

    try:
        rows = read_production_rows(path)
    except Exception as exc:
        print(f"    x Failed to read file: {exc}", file=sys.stderr)
        return {"file": path, "type": "production", "error": str(exc)}

    planned, skipped_zero, unmatched = [], [], []

    for r in rows:
        qty_raw = r["qty"]
        try:
            qty = Decimal(str(qty_raw)) if qty_raw is not None else Decimal("0")
        except Exception:
            qty = Decimal("0")
        if qty <= 0:
            skipped_zero.append(r)
            continue
        product, method, score = matcher.match(r["name"])
        if product is None:
            unmatched.append((r, score))
            print(f"    ? UNMATCHED  {r['name']!r}  (best score {score:.2f}) -- skipped")
            continue
        tag = method if method != "fuzzy" else f"fuzzy {score:.2f}"
        print(f"    * {r['name']:<26} -> {product['name']:<24} x{qty}  [{tag}]")
        planned.append((r, product, qty))

    if limit:
        planned = planned[:limit]

    done, failed = [], []
    if commit and planned:
        print("    Recording runs...")
        for r, product, qty in planned:
            try:
                run = produce_with_topup(api, product, qty, date, materials, log=print)
                done.append((product, qty, run))
                print(f"    + {product['name']} x{qty}  (run {run['id'][:8]}, cost {run['cost']})")
            except (ApiError, RuntimeError) as exc:
                failed.append((product, qty, exc))
                msg = exc.detail if isinstance(exc, ApiError) else str(exc)
                print(f"    x {product['name']} x{qty}  -- {msg}")

    return {
        "file": path,
        "type": "production",
        "planned": len(planned),
        "skipped_zero": len(skipped_zero),
        "unmatched": len(unmatched),
        "done": len(done),
        "failed": len(failed),
    }


def import_expenses_file(
    path: str,
    api: Api,
    wallets_by_name: dict[str, dict],
    existing_refs: set[str],
    categories: list[dict],
    date: str,
    target: str,
    cash_wallet: str,
    default_category: str,
    create_categories: bool,
    allow_duplicates: bool,
    commit: bool,
    limit: int,
) -> dict:
    """Import one expenses Excel file. Returns a result summary dict."""
    print(f"\n  -- Expenses: {os.path.basename(path)}")
    target_desc = (
        "Transactions GUI Page (/transactions)" if target == "transaction"
        else "Expenses (/finance/expenses/)"
    )

    try:
        rows, skipped_voided, skipped_zero = read_expense_rows(path, date)
    except Exception as exc:
        print(f"    x Failed to read file: {exc}", file=sys.stderr)
        return {"file": path, "type": "expenses", "error": str(exc)}

    print(f"    Read {len(rows)} active row(s) "
          f"({skipped_voided} voided skipped, {skipped_zero} zero-amount skipped).")

    if not rows:
        print("    No valid expense rows found to import.")
        return {"file": path, "type": "expenses", "planned": 0,
                "voided": skipped_voided, "zero": skipped_zero,
                "duplicates_skipped": 0, "total_amount": 0.0,
                "done": 0, "failed": 0}

    matcher = CategoryMatcher(categories, CATEGORY_ALIASES, default_name=default_category)

    planned = []
    skipped_duplicates = []
    total_amount = Decimal("0")

    for r in rows:
        exp_id = r["expense_id"]
        if exp_id and exp_id in existing_refs and not allow_duplicates:
            skipped_duplicates.append(r)
            continue

        pm_raw = r["payment_method_raw"].lower()
        payment_method = PAYMENT_METHOD_MAP.get(pm_raw, "cash")
        wallet = resolve_wallet(wallets_by_name, payment_method, cash_wallet_name=cash_wallet)
        cat, match_type, score = matcher.match(r["name"])

        if cat is None and create_categories:
            cat_name = r["name"].strip().capitalize()
            if commit:
                try:
                    if target == "transaction":
                        cat = api.create_transaction_category(
                            cat_name, direction="expense",
                            description="Auto-created during bulk import")
                    else:
                        cat = api.create_expense_category(
                            cat_name, description="Auto-created during bulk import")
                    categories.append(cat)
                    matcher = CategoryMatcher(
                        categories, CATEGORY_ALIASES, default_name=default_category)
                    match_type = "created"
                except ApiError as exc:
                    print(f"    ! Failed to create category {cat_name!r}: {exc.detail}")
            else:
                match_type = "will_create"

        if cat is None:
            cat = matcher.default_category

        notes_parts = []
        if r["time"]:
            notes_parts.append(f"Time: {r['time']}")
        if r["notes"]:
            notes_parts.append(r["notes"])
        final_notes = " | ".join(notes_parts)

        if target == "transaction":
            payload = {
                "direction": "expense",
                "title": r["name"],
                "amount": str(r["amount"]),
                "occurred_on": r["date"],
                "payment_method": payment_method,
                "category": cat["id"] if cat else None,
                "wallet": wallet["id"] if wallet else None,
                "reference": exp_id,
                "notes": final_notes,
            }
        else:
            payload = {
                "title": r["name"],
                "amount": str(r["amount"]),
                "incurred_on": r["date"],
                "payment_method": payment_method,
                "category": cat["id"] if cat else None,
                "wallet": wallet["id"] if wallet else None,
                "reference": exp_id,
                "notes": final_notes,
            }

        tag = match_type if match_type not in ("fuzzy", "fallback") else f"{match_type} {score:.2f}"
        cat_display = cat["name"] if cat else "(none)"
        wallet_display = wallet["name"] if wallet else "(none)"

        print(f"    * {r['name']:<28} {r['amount']:>10} RWF  ->  "
              f"cat: {cat_display:<18} [{payment_method} / {wallet_display}]  [{tag}]")

        planned.append({"row": r, "payload": payload,
                        "cat_name": cat_display, "wallet_name": wallet_display})
        total_amount += r["amount"]

    if limit and limit > 0:
        planned = planned[:limit]

    done, failed = [], []
    if commit and planned:
        print(f"    Recording {len(planned)} transaction(s)...")
        for item in planned:
            r = item["row"]
            payload = item["payload"]
            try:
                if target == "transaction":
                    created = api.create_transaction(payload)
                else:
                    created = api.create_expense(payload)
                done.append((r, created))
                # Track newly imported ref so sibling files in same run don't duplicate
                if created.get("reference"):
                    existing_refs.add(created["reference"].strip())
                ref_str = f" [{created.get('reference')}]" if created.get("reference") else ""
                print(f"    + {created['title']} ({created['amount']} RWF){ref_str} "
                      f"-> {created['category_name']} "
                      f"({created.get('wallet_name') or 'no wallet'})")
            except ApiError as exc:
                failed.append((r, exc))
                print(f"    x {r['name']} ({r['amount']} RWF) -- {exc.detail}")

    return {
        "file": path,
        "type": "expenses",
        "target": target_desc,
        "planned": len(planned),
        "total_amount": float(total_amount),
        "voided": skipped_voided,
        "zero": skipped_zero,
        "duplicates_skipped": len(skipped_duplicates),
        "done": len(done),
        "failed": len(failed),
    }


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        description="Bulk-import multiple Excel files for sales, expenses, and/or production."
    )

    # Connection
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Adminator API base URL.")
    p.add_argument("--email", default=DEFAULT_EMAIL, help="API admin email.")
    p.add_argument("--password", default=DEFAULT_PASSWORD, help="API admin password.")

    # File selection — order of flags on the CLI controls execution order.
    # A custom Action appends (type, [glob, ...]) tuples to args.ordered_inputs
    # in the exact sequence the flags are encountered.
    class _OrderedFileAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if not hasattr(namespace, "ordered_inputs") or namespace.ordered_inputs is None:
                namespace.ordered_inputs = []
            namespace.ordered_inputs.append((self.dest, values))

    p.add_argument("--files", nargs="+", metavar="GLOB", dest="files",
                   action=_OrderedFileAction, default=argparse.SUPPRESS,
                   help="Auto-detect type from filename. Accepts glob patterns.")
    p.add_argument("--sales-files", nargs="+", metavar="GLOB", dest="sales_files",
                   action=_OrderedFileAction, default=argparse.SUPPRESS,
                   help="Sales Excel files or glob patterns.")
    p.add_argument("--expense-files", nargs="+", metavar="GLOB", dest="expense_files",
                   action=_OrderedFileAction, default=argparse.SUPPRESS,
                   help="Expense Excel files or glob patterns.")
    p.add_argument("--production-files", nargs="+", metavar="GLOB", dest="production_files",
                   action=_OrderedFileAction, default=argparse.SUPPRESS,
                   help="Production Excel files or glob patterns.")

    # Common options
    p.add_argument("--date", default=DEFAULT_DATE,
                   help="Fallback date (YYYY-MM-DD) and production scheduled_for date.")
    p.add_argument("--commit", action="store_true",
                   help="Actually write to the database (default: dry-run preview).")
    p.add_argument("--limit", type=int, default=0,
                   help="Only process the first N records per file (testing).")

    # Sales-specific
    p.add_argument("--utc-offset", default=DEFAULT_OFFSET,
                   help="Timezone offset for sales occurred_at (default: Africa/Kigali +02:00).")
    p.add_argument("--use-sheet-prices", action="store_true",
                   help="(Sales) Price each line at Total Price / Qty from the sheet "
                        "instead of the catalog selling price.")

    # Expenses-specific
    p.add_argument("--expense-target", choices=["transaction", "expense"], default="transaction",
                   help="(Expenses) 'transaction' (Transactions GUI page, default) or 'expense'.")
    p.add_argument("--wallet", default=DEFAULT_WALLET,
                   help=f"(Expenses) Cash wallet name (default: {DEFAULT_WALLET}).")
    p.add_argument("--default-category", default=DEFAULT_CATEGORY,
                   help=f"(Expenses) Fallback category name (default: {DEFAULT_CATEGORY}).")
    p.add_argument("--create-categories", action="store_true",
                   help="(Expenses) Auto-create missing categories on the server.")
    p.add_argument("--allow-duplicates", action="store_true",
                   help="(Expenses) Import even if the Expense ID is already in the database.")

    args = p.parse_args()

    # ── build ordered work list (preserves CLI flag sequence) ─────────────────
    # Each entry is (import_type, path) where import_type is one of
    # 'sales', 'expenses', 'production'.
    ordered_work: list[tuple[str, str]] = []
    seen_paths: set[str] = set()

    def _add(import_type: str, path: str) -> None:
        key = os.path.abspath(path)
        if key not in seen_paths:
            seen_paths.add(key)
            ordered_work.append((import_type, path))

    for dest, globs in getattr(args, "ordered_inputs", []):
        expanded = expand_globs(globs)
        if dest == "files":
            for f in expanded:
                t = detect_type(f)
                if t is not None:
                    _add(t, f)
                else:
                    print(
                        f"  ! Could not detect type for {os.path.basename(f)!r} -- skipped. "
                        "Use --sales-files / --expense-files / --production-files to assign it.",
                        file=sys.stderr,
                    )
        elif dest == "sales_files":
            for f in expanded:
                _add("sales", f)
        elif dest == "expense_files":
            for f in expanded:
                _add("expenses", f)
        elif dest == "production_files":
            for f in expanded:
                _add("production", f)

    if not ordered_work:
        p.error(
            "No files specified. Use --files, --sales-files, --expense-files, "
            "or --production-files."
        )

    # Convenience sets for catalog pre-loading
    sales_files      = [p_ for t, p_ in ordered_work if t == "sales"]
    expense_files    = [p_ for t, p_ in ordered_work if t == "expenses"]
    production_files = [p_ for t, p_ in ordered_work if t == "production"]

    mode = "COMMIT" if args.commit else "DRY-RUN (no writes)"
    print(f"Bulk Import  *  {mode}")
    print(f"API    : {args.base_url}")
    print(f"Date   : {args.date}")
    print(f"Files  : {len(sales_files)} sales | {len(expense_files)} expenses "
          f"| {len(production_files)} production  ({len(ordered_work)} total)")
    print(f"  Execution order:")
    for i, (itype, ipath) in enumerate(ordered_work, 1):
        print(f"    {i}. [{itype.upper()}] {os.path.basename(ipath)}")
    print()

    # ── authenticate once ─────────────────────────────────────────────────────
    print("Authenticating...")
    api = Api(args.base_url, args.email, args.password)

    # ── fetch shared catalog data once ────────────────────────────────────────
    print("Loading catalog...")
    products = api.get_all("/catalog/products/")
    materials = index_materials(api.get_all("/inventory/stock/?kind=raw_material"))

    wallets_list = api.get_all("/finance/wallets/")
    wallets_by_name = {w["name"]: w for w in wallets_list}
    # Sales expects wallet name -> id (not full object)
    sales_wallets = {w["name"]: w["id"] for w in wallets_list}

    # Expense categories + existing refs (load once, shared across all expense files)
    if expense_files:
        if args.expense_target == "transaction":
            raw_categories = api.get_all("/finance/transaction-categories/")
            expense_categories = [c for c in raw_categories if c.get("direction") == "expense"]
            existing_expense_records = api.get_all("/finance/transactions/")
        else:
            expense_categories = api.get_all("/finance/expense-categories/")
            existing_expense_records = api.get_all("/finance/expenses/")
        existing_refs: set[str] = {
            e["reference"].strip() for e in existing_expense_records if e.get("reference")
        }
    else:
        expense_categories = []
        existing_refs = set()

    print(f"Loaded {len(products)} products, "
          f"{sum(len(v) for v in materials.values())} stocked materials, "
          f"{len(wallets_list)} wallets.\n")

    # ── run imports in CLI flag order ─────────────────────────────────────────
    results = []

    for import_type, path in ordered_work:
        if import_type == "sales":
            result = import_sales_file(
                path=path,
                api=api,
                products=products,
                materials=materials,
                wallets=sales_wallets,
                date=args.date,
                offset=args.utc_offset,
                use_sheet_prices=args.use_sheet_prices,
                commit=args.commit,
                limit=args.limit,
            )
        elif import_type == "expenses":
            result = import_expenses_file(
                path=path,
                api=api,
                wallets_by_name=wallets_by_name,
                existing_refs=existing_refs,   # mutated in-place as records are created
                categories=expense_categories,
                date=args.date,
                target=args.expense_target,
                cash_wallet=args.wallet,
                default_category=args.default_category,
                create_categories=args.create_categories,
                allow_duplicates=args.allow_duplicates,
                commit=args.commit,
                limit=args.limit,
            )
        elif import_type == "production":
            result = import_production_file(
                path=path,
                api=api,
                products=products,
                materials=materials,
                date=args.date,
                commit=args.commit,
                limit=args.limit,
            )
        else:
            continue
        results.append(result)

    # ── consolidated summary ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Bulk Import Summary")
    print(f"  Mode   : {mode}")
    print(f"  Files  : {len(results)}")
    print()

    any_failed = False

    for r in results:
        label = f"  [{r['type'].upper()}] {os.path.basename(r['file'])}"
        if "error" in r:
            print(f"{label}  ERROR: {r['error']}")
            any_failed = True
            continue

        if r["type"] == "sales":
            print(label)
            print(f"      planned  : {r['planned']}  |  "
                  f"done: {r.get('done', '--')}  |  failed: {r.get('failed', '--')}")
            print(f"      voided lines: {r['voided']}  |  CEVR skipped: {r['cevr_skipped']}  |  "
                  f"unmatched: {r['unmatched']}  |  bad orders: {r['bad_orders']}")
            totals = r.get("totals", {})
            grand = sum(totals.values())
            print(f"      totals   : MoMo {totals.get('mobile_money', 0):.2f}  "
                  f"Cash {totals.get('cash', 0):.2f}  Card {totals.get('card', 0):.2f}  "
                  f"-> TOTAL {grand:.2f}")
            if r.get("failed"):
                any_failed = True

        elif r["type"] == "production":
            print(label)
            print(f"      planned  : {r['planned']}  |  "
                  f"done: {r.get('done', '--')}  |  failed: {r.get('failed', '--')}")
            print(f"      skipped (no qty): {r['skipped_zero']}  |  unmatched: {r['unmatched']}")
            if r.get("failed"):
                any_failed = True

        elif r["type"] == "expenses":
            print(label)
            print(f"      target   : {r.get('target', '--')}")
            print(f"      planned  : {r['planned']}  "
                  f"(total: {r.get('total_amount', 0):,.2f} RWF)  |  "
                  f"done: {r.get('done', '--')}  |  failed: {r.get('failed', '--')}")
            print(f"      voided: {r['voided']}  |  zero amount: {r['zero']}  |  "
                  f"duplicates skipped: {r['duplicates_skipped']}")
            if r.get("failed"):
                any_failed = True

    print()
    if not args.commit:
        print("  DRY-RUN -- nothing written. Re-run with --commit to record everything above.")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
