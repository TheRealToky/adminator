#!/usr/bin/env python3
r"""Import bulk expenses from an Excel sheet into Adminator.

Reads an Excel workbook (sheet named "Expenses" by default) with 8 columns:
  1. Expense ID      - Unique reference for the expense (e.g. EXP-2026-001)
  2. Name            - Title / description of the expense
  3. Amount (RWF)    - Total amount spent in Rwandan Francs
  4. Payment Method  - Settlement method (e.g. "Cash", "MoMo", "Card")
  5. Time            - Time of transaction (e.g. 14:30)
  6. Date            - Date of expense (YYYY-MM-DD)
  7. Status          - Row status (e.g. "Paid", "Completed", "Voided")
  8. Notes           - Free-form remarks or notes

Business rules & edge cases handled
------------------------------------
* **GUI Transactions Page Support (Default)**:
  By default, expenses are recorded as **Transactions** (``direction = "expense"``)
  at ``POST /finance/transactions/`` so they show up directly on the GUI
  **Transactions** page (``/transactions``). Use ``--target expense`` to record
  as standalone ``Expense`` models instead.
* **Wallet Routing by Payment Method**:
  - **Cash** -> **"Petite caisse"** by default (configurable via ``--wallet``).
  - **MoMo / Mobile Money** -> **"Mobile money balance"** (with fallback to active mobile money wallet).
  - **Card / POS** -> **"Bank"** (with fallback to bank/card float wallets).
* **Category Matching**: Expense names are resolved against the existing
  transaction categories: exact category name, then the ordered keyword rules in
  ``CATEGORY_RULES`` (whole-word, accent-insensitive, first match wins), then a
  typo-tolerant pass. Titles that match nothing fall back to ``Others`` and are
  listed in the summary so you can add a rule for them.
* **Idempotency & Duplicate Protection**: Existing transactions/expenses in the
  database are checked by their ``Expense ID`` reference so re-running the script
  skips already imported rows safely (override with ``--allow-duplicates``).
* **Voided / Cancelled Rows**: Rows marked as "Voided" or "Cancelled" in the
  ``Status`` column are automatically skipped and tallied in the summary.
* **Zero or Invalid Amounts**: Rows with blank, zero, or negative amounts are
  reported and skipped.

Safe by default: runs in **dry-run** mode (parses, matches, and displays the plan
without making any API writes). Pass ``--commit`` to actually record the expenses.

Usage
-----
    # Preview import into Transactions page (dry-run, no writes):
    python scripts/import_expenses.py --file path/to/expenses.xlsx

    # Commit import to database (shows on /transactions):
    python scripts/import_expenses.py --file path/to/expenses.xlsx --commit

    # Custom API target / fallback date / limit:
    python scripts/import_expenses.py --commit \
        --file "D:\data\expenses.xlsx" \
        --base-url http://localhost:8001/api/v1 \
        --wallet "Petite caisse" \
        --date 2026-08-12 \
        --limit 10

Requirements (host): ``pip install openpyxl`` (HTTP uses standard library urllib).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher, get_close_matches

try:
    import openpyxl
except ModuleNotFoundError:
    sys.exit("openpyxl is not installed.\n  Fix: python -m pip install openpyxl")

# ── defaults (override on CLI or via env) ────────────────────────────────────
DEFAULT_BASE_URL = os.environ.get("ADMINATOR_API", "http://localhost:8001/api/v1")
DEFAULT_EMAIL = os.environ.get("ADMINATOR_EMAIL", "admin@adminator.local")
DEFAULT_PASSWORD = os.environ.get("ADMINATOR_PASSWORD", "admin12345")
DEFAULT_FILE = os.environ.get(
    "EXPENSES_XLSX",
    r"D:\PC DISAINE\toky\Perso-D\red\sales\sales_books\pastry_expenses_2026-10-09_to_2026-10-12.xlsx",
)
DEFAULT_DATE = datetime.date.today().isoformat()
DEFAULT_WALLET = "Petite caisse"
DEFAULT_CATEGORY = "Others"

SHEET_NAME = "Expenses"

# Status values that indicate the row should NOT be imported
SKIP_STATUSES = {"voided", "cancelled", "annule", "annulé", "rejected", "deleted"}

# Payment method aliases mapping sheet values to API choices
# Backend choices: "cash", "mobile_money", "card", "bank_transfer"
PAYMENT_METHOD_MAP = {
    "cash": "cash",
    "espece": "cash",
    "espèces": "cash",
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

# Default wallet for each payment method
WALLET_FOR_METHOD = {
    "cash": "Petite caisse",
    "mobile_money": "Mobile money balance",
    "card": "Bank",
    "bank_transfer": "Bank",
}

# ── category classification ──────────────────────────────────────────────────
# Rules are tried top to bottom and the FIRST rule whose keywords appear in the
# title wins, so the order below is the priority order:
#   * "money / overhead" words beat product words, e.g. "Transport for flour"
#     -> Transportation (not Flour), "Momo fees" -> Fees, "Nancy salary" -> Salary;
#   * packaging / cleaning words beat product words ("Coffee cup" -> Supplies,
#     "Milk powder" -> Supplies, not Coffee / Dairy);
#   * Vegetables beat Fruits ("Fruits and vegetables" -> Vegetables).
# Keywords are matched as WHOLE WORDS on the normalized title (lowercase, no
# accents, punctuation ignored); a plural -s / -es is tolerated automatically.
# Targets are the category names of the Transactions page. A rule whose target
# is missing in the database is skipped and reported once at start-up, so edit
# the names here if you rename a category.
CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Salary", (
        "salary", "salaries", "salaire", "payroll", "wage", "wages",
        "management accounting services",
    )),
    ("Transportation", (
        "transport", "transportation", "moto", "motorbike", "motorcycle",
        "motari", "taxi", "ticket", "bus", "fare", "parking", "delivery",
        "livraison", "uber", "yego", "fuel", "petrol", "diesel", "carburant",
        "location voiture", "car rental", "car hire", "flight", "shipping",
    )),
    ("Taxes", (
        "tax", "impot", "vat", "tva", "license", "licence", "patente",
        "rssb", "rra", "iqp", "cit", "social security",
    )),
    ("Fees", (
        "momo fee", "mobile money fee", "momo charge", "bank fee",
        "bank charge", "transaction fee", "withdrawal fee", "transfer fee",
        "commission", "fee",
    )),
    ("Rent", ("rent", "loyer")),
    ("Gas", ("gas", "gaz", "butane", "lpg")),
    ("Services", (
        "fumigation", "pest control", "printing", "print", "enseigne",
        "panneau", "signage", "signboard", "vitrerie", "plumber", "plumbing",
        "electrician", "maintenance", "repair", "reparation", "technician",
        "technicien", "fridge", "hood", "spot light", "spotlight", "filter",
        "borderie", "embroidery", "installation", "welding", "carpenter",
    )),
    ("Drinks", (
        "inyange water", "sparkling water", "mineral water", "bottled water",
        "drinking water", "water bottle", "vitalo", "coca", "coca cola",
        "fanta", "sprite", "pepsi", "mirinda", "soda", "juice", "lemonade",
        "beverage", "drink", "beer", "wine",
    )),
    ("Subscriptions", (
        "electricity", "electricite", "cash power", "cashpower", "wifi",
        "internet", "wasac", "regideso", "canalbox", "airtime", "telephone",
        "subscription", "security", "water", "insurance", "assurance",
        "hosting",
    )),
    # Packaging / cleaning / consumables: must come BEFORE the food groups
    ("Supplies", (
        "cup", "lid", "bag", "box", "cake board", "cake box", "packaging",
        "envelope", "napkin", "serviette", "straw", "foil", "film",
        "cling film", "baking sheet", "parchment", "ribbon", "ruban", "label",
        "sticker", "decoration", "cap", "bouffant", "lighter", "soap",
        "detergent", "javel", "bleach", "sponge", "glove", "cleaning",
        "nettoyage", "savon", "tissue", "toilet paper", "paper", "papier",
        "stationery", "printer ink", "ink", "toner", "milk powder",
        "peanut butter",
    )),
    ("Meats", (
        "meat", "chicken", "ham", "jambo", "sardine", "beef", "fillet",
        "filet", "butcher", "pork", "sausage", "saucisse", "bacon", "fish",
        "poisson", "salami", "lamb", "goat", "turkey", "mince", "viande",
        "poulet", "boeuf", "porc", "jambon",
    )),
    ("Eggs", ("egg", "oeuf")),
    ("Dairy", (
        "milk", "butter", "cheese", "chesse", "yoghurt", "yogurt",
        "youghurt", "yoghourt", "cream", "dairy", "dairies", "lait",
        "beurre", "fromage", "yaourt", "cheddar", "mozzarella", "parmesan",
        "feta", "gouda", "masaka", "ishyo",
    )),
    ("Coffee", ("coffee", "cafe", "espresso", "arabica", "nescafe")),
    ("Vegetables", (
        "vegetable", "legume", "lettuce", "dodo", "tomato", "tomate",
        "potato", "patate", "ginger", "gingembre", "cucumber", "concombre",
        "onion", "oignon", "carrot", "carotte", "garlic", "poivron",
        "bell pepper", "green pepper", "cabbage", "chou", "spinach",
        "epinard", "eggplant", "aubergine", "zucchini", "courgette", "celery",
        "leek", "poireau", "beetroot", "pumpkin", "mushroom", "champignon",
        "bean", "haricot", "peas", "nuts", "nut", "peanut", "sesame", "herbs",
        "coriander", "parsley", "mint", "basil", "cassava", "manioc",
    )),
    ("Fruits", (
        "fruit", "avocado", "avocat", "banana", "banane", "mango", "mangue",
        "lemon", "citron", "lime", "apple", "pomme", "strawberry",
        "strawberries", "berry", "berries", "fraise", "passion", "orange",
        "raisin", "grape", "pineapple", "ananas", "papaya", "papaye",
        "watermelon", "melon", "pear", "peach", "guava", "kiwi", "coconut",
    )),
    ("Flour", ("flour", "farine", "azam", "maize", "cornmeal", "semolina")),
    # Pantry staples + known grocery suppliers (after the food groups so that
    # e.g. "Vegetables groceries" stays Vegetables)
    ("Supplies", (
        "groceries", "grocery", "epicerie", "supply", "supplies", "achat",
        "sugar", "sucre", "salt", "sel", "oil", "huile", "baking powder",
        "yeast", "vanilla", "cinnamon", "honey", "miel", "ketchup",
        "mustard", "moutarde", "mayonnaise", "sauce", "vinegar", "rice",
        "riz", "custard", "chocolate", "cocoa", "cacao", "spice", "pepper",
        "starch", "gelatin", "sprinkles", "icing", "food colouring",
        "food coloring", "milimani", "henok", "hyab", "shyaka", "simba",
        "delicenature", "wow market", "trendy", "kazuri", "onintsiky",
        "kinazi",
    )),
]

# Whole-title shortcuts (normalized title -> category) for things that are only
# right when they are the ENTIRE title, e.g. "Toky change" must not match.
EXACT_TITLES: dict[str, str] = {
    "change": "Change",
    "money change": "Change",
    "cash change": "Change",
}

# Typo tolerance: when no rule matches, each word of 5+ letters is compared
# with the single-word keywords above; >= this similarity counts as a hit
# (e.g. "youghurt" -> yoghurt, "tomatos" -> tomato). Raise it if it misfires.
TYPO_CUTOFF = 0.84


# ── helpers ──────────────────────────────────────────────────────────────────
def normalize(text: str | None) -> str:
    """Lowercase, remove accents and punctuation, reduce whitespace."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(date_val, fallback_date: str) -> str:
    """Extract standard YYYY-MM-DD date string."""
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        return date_val.strftime("%Y-%m-%d")
    if date_val is not None:
        s = str(date_val).strip()
        # YYYY-MM-DD or YYYY/MM/DD
        m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # DD-MM-YYYY or DD/MM/YYYY
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
                    h, m = int(parts[0]), int(parts[1])
                    return f"{h:02d}:{m:02d}:00"
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


# ── API client ───────────────────────────────────────────────────────────────
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


# ── category resolution ──────────────────────────────────────────────────────
def _rule_regex(keywords) -> "re.Pattern":
    """Whole-word regex for a keyword list; tolerates a plural -s / -es."""
    alts = sorted({normalize(k) for k in keywords if normalize(k)},
                  key=len, reverse=True)
    return re.compile(
        r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts)
        + r")(?:s|es)?(?![a-z0-9])"
    )


class CategoryMatcher:
    """Classify an expense title into one of the database categories.

    Order of attempts:
      1. title equals a category name              -> "exact"
      2. title is in EXACT_TITLES                  -> "alias"
      3. first CATEGORY_RULES rule that matches    -> "rule"
      4. misspelt keyword (similarity >= cutoff)   -> "typo"
      5. nothing matched                           -> default category ("fallback")
    """

    def __init__(self, categories: list[dict], rules=None,
                 default_name: str = DEFAULT_CATEGORY, exact_titles=None):
        rules = CATEGORY_RULES if rules is None else rules
        exact_titles = EXACT_TITLES if exact_titles is None else exact_titles
        self.categories = categories
        self.by_norm: dict[str, dict] = {normalize(c["name"]): c for c in categories}

        # Rules whose target category is not in the database are skipped, but
        # remembered so the caller can warn (they used to vanish silently).
        self.rules: list[tuple[dict, "re.Pattern"]] = []
        self.missing_targets: list[str] = []
        self._vocab: dict[str, dict] = {}
        for target, keywords in rules:
            cat = self.by_norm.get(normalize(target))
            if cat is None:
                if target not in self.missing_targets:
                    self.missing_targets.append(target)
                continue
            self.rules.append((cat, _rule_regex(keywords)))
            for kw in keywords:
                nk = normalize(kw)
                if " " not in nk and len(nk) >= 5:
                    self._vocab.setdefault(nk, cat)   # earlier rule = higher priority

        self.exact_titles: dict[str, dict] = {}
        for title, cat_name in exact_titles.items():
            cat = self.by_norm.get(normalize(cat_name))
            if cat:
                self.exact_titles[normalize(title)] = cat

        self.default_category = (
            self.by_norm.get(normalize(default_name))
            or self.by_norm.get("others")
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
        if n in self.exact_titles:
            return self.exact_titles[n], "alias", 1.0
        for cat, rx in self.rules:
            if rx.search(n):
                return cat, "rule", 1.0
        best, best_score = None, 0.0
        for tok in n.split():
            if len(tok) < 5 or tok.isdigit():
                continue
            for hit in get_close_matches(tok, self._vocab, n=1, cutoff=TYPO_CUTOFF):
                score = SequenceMatcher(None, tok, hit).ratio()
                if score > best_score:
                    best, best_score = self._vocab[hit], score
        if best:
            return best, "typo", best_score
        if self.default_category:
            return self.default_category, "fallback", 0.0
        return None, "unmatched", 0.0


# ── spreadsheet parser ───────────────────────────────────────────────────────
def read_expense_sheet(path: str, fallback_date: str) -> tuple[list[dict], int, int]:
    """Parse Excel workbook into structured rows.

    Returns:
        (rows, skipped_voided_count, skipped_zero_count)
    """
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.worksheets[0]
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

    parsed_rows = []
    skipped_voided = 0
    skipped_zero = 0

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

        # Skip rows without a name or title
        if not name or str(name).strip() == "":
            continue

        name_clean = str(name).strip()
        status_clean = str(status_raw or "").strip().lower()

        # Check voided / cancelled
        if status_clean in SKIP_STATUSES:
            skipped_voided += 1
            continue

        amount = parse_amount(amount_raw)
        if amount <= Decimal("0"):
            skipped_zero += 1
            continue

        incurred_on = parse_date(date_raw, fallback_date)
        time_str = parse_time(time_raw)
        exp_id_str = str(exp_id).strip() if exp_id is not None else ""
        notes_str = str(notes_raw).strip() if notes_raw is not None else ""

        parsed_rows.append({
            "row_num": i,
            "expense_id": exp_id_str,
            "name": name_clean,
            "amount": amount,
            "payment_method_raw": str(method_raw or "").strip(),
            "time": time_str,
            "date": incurred_on,
            "status": status_clean,
            "notes": notes_str,
        })

    return parsed_rows, skipped_voided, skipped_zero


# ── wallet resolution ────────────────────────────────────────────────────────
def resolve_wallet(
    wallets_by_name: dict[str, dict],
    payment_method: str,
    cash_wallet_name: str = DEFAULT_WALLET,
) -> dict | None:
    """Find the target wallet for an expense based on its payment method.

    - Cash -> cash_wallet_name (default: "Petite caisse")
    - Mobile money (Momo) -> "Mobile money balance"
    - Card -> "Bank"
    - Bank transfer -> "Bank"
    """
    target_wallet_name = (
        cash_wallet_name if payment_method == "cash" else WALLET_FOR_METHOD.get(payment_method, "Petite caisse")
    )

    # 1. Exact match on target wallet name
    if target_wallet_name in wallets_by_name:
        return wallets_by_name[target_wallet_name]

    # 2. Case/accent-insensitive match on target wallet name
    norm_target = normalize(target_wallet_name)
    for name, w in wallets_by_name.items():
        if normalize(name) == norm_target:
            return w

    # 3. Known fallback aliases per payment method
    fallback_aliases = {
        "mobile_money": ["Mobile money balance", "MTN Mobile Money", "Mobile Money", "MoMo"],
        "card": ["Bank", "Bank of Kigali — current", "Card terminal float", "Bank Account"],
        "bank_transfer": ["Bank", "Bank of Kigali — current", "Bank Account"],
        "cash": [cash_wallet_name, "Petite caisse", "Petty cash", "Front-counter drawer", "Caisse"],
    }
    for alias in fallback_aliases.get(payment_method, []):
        norm_alias = normalize(alias)
        for name, w in wallets_by_name.items():
            if normalize(name) == norm_alias:
                return w

    # 4. Fallback: match by wallet account_type
    target_type = "mobile_money" if payment_method == "mobile_money" else ("cash" if payment_method == "cash" else "bank")
    for w in wallets_by_name.values():
        if w.get("account_type") == target_type and w.get("is_active", True):
            return w

    # 5. Return first available wallet if any
    return next(iter(wallets_by_name.values()), None) if wallets_by_name else None


# ── main logic ───────────────────────────────────────────────────────────────
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        description="Import bulk expenses from an Excel sheet into Adminator."
    )
    p.add_argument("--file", default=DEFAULT_FILE, help=f"Path to expenses Excel file (default: {DEFAULT_FILE}).")
    p.add_argument("--target", choices=["transaction", "expense"], default="transaction",
                   help="Target model: 'transaction' (shows on GUI Transactions page, default) or 'expense'.")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Adminator API base URL.")
    p.add_argument("--email", default=DEFAULT_EMAIL, help="API admin email.")
    p.add_argument("--password", default=DEFAULT_PASSWORD, help="API admin password.")
    p.add_argument("--date", default=DEFAULT_DATE, help="Fallback date (YYYY-MM-DD) if Date column is empty.")
    p.add_argument("--wallet", default=DEFAULT_WALLET, help=f"Cash wallet name to assign cash expenses to (default: {DEFAULT_WALLET}).")
    p.add_argument("--default-category", default=DEFAULT_CATEGORY, help=f"Fallback category name (default: {DEFAULT_CATEGORY}).")
    p.add_argument("--create-categories", action="store_true", help="Auto-create missing categories on the server.")
    p.add_argument("--allow-duplicates", action="store_true", help="Import even if Expense ID is already in the database.")
    p.add_argument("--commit", action="store_true", help="Actually write to the database (default: dry-run preview).")
    p.add_argument("--limit", type=int, default=0, help="Only process the first N expenses (testing).")
    args = p.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN (no writes)"
    target_desc = "Transactions GUI Page (/transactions)" if args.target == "transaction" else "Expenses (/finance/expenses/)"
    print(f"Expense Import · {mode}")
    print(f"Target : {target_desc}")
    print(f"File   : {args.file}")
    print(f"Wallets: Cash -> {args.wallet} | Momo -> Mobile money balance | Card -> Bank")
    print(f"API    : {args.base_url}\n")

    # 1. Parse Excel rows
    rows, skipped_voided, skipped_zero = read_expense_sheet(args.file, args.date)
    print(f"Read {len(rows)} active expense row(s) from sheet "
          f"({skipped_voided} voided/cancelled skipped, {skipped_zero} zero/empty amount skipped).\n")

    if not rows:
        print("No valid expense rows found to import.")
        return 0

    # 2. Authenticate and load remote catalog & state
    api = Api(args.base_url, args.email, args.password)

    wallets_list = api.get_all("/finance/wallets/")
    wallets_by_name = {w["name"]: w for w in wallets_list}

    if args.target == "transaction":
        raw_categories = api.get_all("/finance/transaction-categories/")
        # Filter for expense direction or active
        categories = [c for c in raw_categories if c.get("direction") == "expense"]
        existing_records = api.get_all("/finance/transactions/")
    else:
        categories = api.get_all("/finance/expense-categories/")
        existing_records = api.get_all("/finance/expenses/")

    # Fetch existing refs to guard against duplicates
    existing_refs = {e["reference"].strip() for e in existing_records if e.get("reference")}

    # Ensure a default category exists if database has none
    if not categories:
        if args.target == "transaction":
            print("  ! No expense transaction categories found in database. Initializing default 'Other' category...")
            if args.commit:
                try:
                    default_cat = api.create_transaction_category(args.default_category, direction="expense")
                    categories.append(default_cat)
                except ApiError as exc:
                    print(f"  ! Warning: could not initialize category: {exc.detail}")
        else:
            print("  ! No expense categories found in database. Initializing default 'Other' category...")
            if args.commit:
                try:
                    default_cat = api.create_expense_category(args.default_category)
                    categories.append(default_cat)
                except ApiError as exc:
                    print(f"  ! Warning: could not initialize category: {exc.detail}")

    matcher = CategoryMatcher(categories, CATEGORY_RULES, default_name=args.default_category)
    if matcher.missing_targets:
        print("  ! Category rules skipped (no such category in the database): "
              + ", ".join(matcher.missing_targets))
        print("    Create them in the app or edit CATEGORY_RULES; those titles fall back to "
              f"{args.default_category!r}.\n")

    # 3. Plan import items
    planned = []
    skipped_duplicates = []
    total_amount = Decimal("0")

    for r in rows:
        exp_id = r["expense_id"]

        # Duplicate check by Expense ID reference
        if exp_id and exp_id in existing_refs and not args.allow_duplicates:
            skipped_duplicates.append(r)
            continue

        # Resolve Payment Method & Wallet
        pm_raw = r["payment_method_raw"].lower()
        payment_method = PAYMENT_METHOD_MAP.get(pm_raw, "cash")
        wallet = resolve_wallet(wallets_by_name, payment_method, cash_wallet_name=args.wallet)

        # Resolve Category
        cat, match_type, score = matcher.match(r["name"])

        if cat is None and args.create_categories:
            cat_name = r["name"].strip().capitalize()
            if args.commit:
                try:
                    if args.target == "transaction":
                        cat = api.create_transaction_category(cat_name, direction="expense", description="Auto-created during bulk import")
                    else:
                        cat = api.create_expense_category(cat_name, description="Auto-created during bulk import")
                    categories.append(cat)
                    matcher = CategoryMatcher(categories, CATEGORY_RULES, default_name=args.default_category)
                    match_type = "created"
                except ApiError as exc:
                    print(f"  ! Failed to create category {cat_name!r}: {exc.detail}")
            else:
                match_type = "will_create"

        if cat is None:
            cat = matcher.default_category

        # Build notes & reference
        notes_parts = []
        if r["time"]:
            notes_parts.append(f"Time: {r['time']}")
        if r["notes"]:
            notes_parts.append(r["notes"])
        final_notes = " | ".join(notes_parts)

        if args.target == "transaction":
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

        tag = (f"typo {score:.2f}" if match_type == "typo"
               else "fallback - review" if match_type == "fallback" else match_type)
        cat_display = cat["name"] if cat else "(none)"
        wallet_display = wallet["name"] if wallet else "(none)"

        print(f"  • {r['name']:<28} {r['amount']:>10} RWF  →  cat: {cat_display:<18} "
              f"[{payment_method} / {wallet_display}]  [{tag}]")

        planned.append({
            "row": r,
            "payload": payload,
            "cat_name": cat_display,
            "wallet_name": wallet_display,
            "match_type": match_type,
        })
        total_amount += r["amount"]

    if args.limit and args.limit > 0:
        planned = planned[: args.limit]

    # 4. Execute writes if --commit
    done, failed = [], []

    if args.commit and planned:
        print(f"\nRecording {len(planned)} transaction(s) on the Transactions page…")
        for item in planned:
            r = item["row"]
            payload = item["payload"]
            try:
                if args.target == "transaction":
                    created = api.create_transaction(payload)
                else:
                    created = api.create_expense(payload)
                done.append((r, created))
                ref_str = f" [{created.get('reference')}]" if created.get("reference") else ""
                print(f"  ✓ {created['title']} ({created['amount']} RWF){ref_str} "
                      f"→ {created['category_name']} ({created.get('wallet_name') or 'no wallet'})")
            except ApiError as exc:
                failed.append((r, exc))
                print(f"  ✗ {r['name']} ({r['amount']} RWF) — {exc.detail}")

    # 5. Print summary
    print("\n" + "=" * 66)
    print("Summary")
    print(f"  target destination    : {target_desc}")
    print(f"  total rows parsed     : {len(rows)}")
    print(f"  records planned       : {len(planned)}  (total: {total_amount:,.2f} RWF)")
    print(f"  voided/cancelled      : {skipped_voided}")
    print(f"  zero/invalid amount   : {skipped_zero}")
    fallback_titles = sorted({i["row"]["name"] for i in planned if i["match_type"] == "fallback"})
    print(f"  no category rule hit  : {len(fallback_titles)} title(s) -> {args.default_category!r}"
          + (f"  → {', '.join(fallback_titles[:10])}" + (" …" if len(fallback_titles) > 10 else "")
             if fallback_titles else ""))
    print(f"  duplicates skipped    : {len(skipped_duplicates)}"
          + (f"  → {', '.join(x['expense_id'] for x in skipped_duplicates[:5])}" if skipped_duplicates else ""))

    if args.commit:
        print(f"  records created       : {len(done)}")
        print(f"  records failed        : {len(failed)}")
    else:
        print("\n  DRY-RUN — nothing written. Re-run with --commit to record these on the Transactions page.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())