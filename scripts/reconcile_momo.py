#!/usr/bin/env python3
r"""Reconcile a MoMo statement against the sales book(s) for the same day(s).

Answers two questions at once:

* **Did every MoMo order in the book actually get paid?** — orders the book
  marks ``MoMo`` with no matching money-in on the statement.
* **Did every MoMo payment get written down?** — money that landed in the
  account with no order in the book. These are the *unrecorded* sales: takings
  the shop received but never rang up.

How a transaction is linked to an order
---------------------------------------
**Time is the primary key, amount is the secondary one.** An order and a
transaction are eligible to pair up when they fall on the same day and their
times are within ``--tolerance`` minutes of each other (default ±5) — the book
is written by hand at minute precision, and the phone timestamps the payment a
little before or after the order is entered. Among the eligible pairs the amount
decides, in two passes:

1. **exact pass** — only pairs whose amounts are equal. These are the
   confident matches, so they get first claim on both sides.
2. **loose pass** — whatever is left over pairs on time alone, and any amount
   difference is reported as a *discrepancy* to eyeball (a mis-keyed price, a
   forgotten line, a tip).

Each pass solves the whole day at once rather than walking the list top to
bottom: pairs are considered cheapest first (smallest time gap, then smallest
amount gap) but the assignment is chosen to link as many pairs as possible, so
two customers paying in the same minute don't leave one of them stranded and
falsely flagged as unrecorded.

What is counted
---------------
From the statement: **successful incoming money** only, and only the types a
customer can pay with — ``PAYMENT`` (a MoMo tap) and ``TRANSFER`` (a bank or
EKash push, which settles under its own type but is just as much a sale).
Balance enquiries (``LAST_TRANSACTIONS``), agent float (``CASH_IN``), payments
the shop *sent*, and ``FAILED`` attempts are not sales and are left out — they
are tallied on their own line so the numbers still add up against the PDF.
Anything that settled as something other than a plain MoMo payment is tagged
``[transfer]`` in the report, so a bank-pushed sale stays visible as one.

From the book: non-voided lines whose Payment Method is **MoMo**, summed per
**Order Id** — the same grouping ``import_sales.py`` uses, so the MoMo total
here matches the book's own "Day Summary". Voided orders are excluded but kept
to one side: if a voided order was in fact paid for, its money shows up as an
unrecorded transaction, so any unrecorded transaction that lines up with a
voided order says so.

Only days that have a sales book are reconciled. A statement usually spans a
week, so transactions on days with no book are reported separately instead of
being flagged as unrecorded — pass more ``--book`` files to cover them.

Read-only: this never writes to the backend and never edits the inputs.

Usage
-----
    python scripts/reconcile_momo.py --statement momo.pdf --book sales.xlsx
    python scripts/reconcile_momo.py --book 2026-07/*.xlsx     # a whole week
    python scripts/reconcile_momo.py --tolerance 10            # looser window
    python scripts/reconcile_momo.py --matched                 # show every link
    python scripts/reconcile_momo.py --csv reconciliation.csv
    python scripts/reconcile_momo.py --json

Requirements (host): ``pip install pdfplumber openpyxl``.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict
from decimal import Decimal, InvalidOperation

try:
    import pdfplumber
except ModuleNotFoundError:
    sys.exit('pdfplumber is not installed.\n  Fix: python -m pip install pdfplumber')

try:
    import openpyxl
except ModuleNotFoundError:
    sys.exit('openpyxl is not installed.\n  Fix: python -m pip install openpyxl')

# ── defaults (override on the CLI or via env) ────────────────────────────────
DEFAULT_STATEMENT = os.environ.get(
    "MOMO_STATEMENT_PDF",
    r"D:\PC DISAINE\toky\Perso-D\red\momo\transaction-history-20261012_101751384.pdf"
)
DEFAULT_BOOK = os.environ.get(
    "SALES_XLSX",
    r"D:\PC DISAINE\toky\Perso-D\red\sales\sales_books\2026-10\pastry_sales_2026-10-10.xlsx"
)
DEFAULT_TOLERANCE_MIN = 5
# An unmatched order is told about the closest same-amount payment either way.
# Past this gap it is reported as information only, without suggesting a wider
# --tolerance: two sales that far apart are different customers, not one wobbly
# clock, and widening the window that much would start inventing matches.
NEAR_MISS_SUGGEST_MIN = 30
SHEET_NAME = "Sales Lines"
CURRENCY = "RWF"

# Book columns we care about, by header name (the sheet is read by header, not
# by position, so an extra column upstream doesn't silently shift everything).
BOOK_COLUMNS = {
    "order": "Order Id",
    "label": "Order Label",
    "product": "Product Name",
    "qty": "Qty",
    "method": "Payment Method",
    "time": "Time",
    "date": "Date",
    "total": "Total Price",
    "status": "Status",
}
MOMO_METHOD = "momo"          # Payment Method value that settles into MoMo
VOIDED_STATUS = "voided"      # book Status for a line that was rung up then cancelled

# Statement rows that represent a customer paying the shop. Everything else is
# money the shop moved itself, or not money at all. A bank or EKash push lands
# as TRANSFER rather than PAYMENT — same sale, different rail — so both count
# once the direction check says the money came in.
SALE_TXN_TYPES = {"PAYMENT", "TRANSFER"}
PLAIN_TXN_TYPE = "PAYMENT"    # the unremarkable one; the rest are tagged in the report
SUCCESSFUL = "SUCCESSFUL"


# ── small helpers ────────────────────────────────────────────────────────────
def money(value) -> str:
    return f"{Decimal(value):,.0f} {CURRENCY}"


def parse_amount(raw) -> Decimal:
    """'12,500' / '12500.00' / 12500 → Decimal. Blank or junk → 0.

    Whole amounts are normalised to have no fractional part, so a cell Excel
    handed over as ``7500.0`` compares and prints the same as ``7500``.
    """
    if raw is None:
        return Decimal("0")
    text = re.sub(r"[^\d.\-]", "", str(raw))
    if not text or text in {"-", ".", "-."}:
        return Decimal("0")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return Decimal("0")
    return value.to_integral_value() if value == value.to_integral_value() else value


def plain(value) -> str:
    """Render a cell for display, dropping the ``.0`` Excel adds to whole
    numbers so Order Id 96 doesn't read as 'order 96.0'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return str(int(value))
    return "" if value is None else str(value).strip()


def parse_book_time(raw) -> dt.time | None:
    """The Time column is usually the string 'HH:MM', but Excel turns some cells
    into real times. Accept both, plus 'HH:MM:SS'."""
    if raw is None:
        return None
    if isinstance(raw, dt.datetime):
        return raw.time()
    if isinstance(raw, dt.time):
        return raw
    text = str(raw).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_book_date(raw) -> dt.date | None:
    if raw is None:
        return None
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    try:
        return dt.date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def name_tokens(value: str) -> set[str]:
    """Comparable word set for an account holder, ignoring case and 'Ltd'."""
    words = re.findall(r"[a-z0-9]+", str(value).lower())
    return {w for w in words if w not in {"ltd", "limited", "sarl", "plc"}}


# ── the MoMo statement (PDF) ─────────────────────────────────────────────────
def read_statement(path: str, business: str | None = None) -> tuple[list[dict], dict]:
    """Parse the statement into transaction dicts plus a bit of header metadata.

    Rows are extracted per page and the repeated column header is dropped. When
    a row's wrapped text spills over a page break the overflow arrives as a row
    with an empty Transaction Id — it is folded back into the row above rather
    than counted as a transaction of its own.
    """
    rows: list[list[str]] = []
    header_text = ""
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages):
            if page_no == 0:
                header_text = page.extract_text() or ""
            for raw in page.extract_table() or []:
                cells = [(c or "").strip() for c in raw]
                if not cells or cells[0].startswith("Transaction"):
                    continue          # repeated column header
                if not cells[0]:
                    if rows:          # continuation of the row above
                        for i, cell in enumerate(cells):
                            if cell:
                                rows[-1][i] = f"{rows[-1][i]}\n{cell}".strip()
                    continue
                rows.append(cells)

    meta = {"path": path, "rows": len(rows)}
    for key, pattern in (("customer", r"Customer:\s*(.+)"),
                         ("number", r"Number:\s*(\S+)"),
                         ("period", r"Period:\s*(.+)"),
                         ("generated", r"Generated:\s*(.+)")):
        found = re.search(pattern, header_text)
        meta[key] = found.group(1).strip() if found else ""
    declared = re.search(r"Total Transactions:\s*(\d+)", header_text)
    meta["declared_total"] = int(declared.group(1)) if declared else None

    # Which side of a row is "us": the account named in the statement header,
    # unless the caller overrides it.
    business = business or meta.get("customer") or ""
    ours = name_tokens(business) | ({meta["number"]} if meta.get("number") else set())
    if not ours:
        sys.exit("Could not work out whose statement this is. Pass --business.")

    def is_us(cell: str) -> bool:
        return bool(ours & (name_tokens(cell) | set(re.findall(r"\d{6,}", cell))))

    transactions, other = [], []
    for cells in rows:
        txn_id, status, txn_type, when_raw, sender, receiver, amount = cells[:7]
        when = None
        try:
            when = dt.datetime.strptime(when_raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        incoming = is_us(receiver) and not is_us(sender)
        record = {
            "id": txn_id,
            "status": status,
            "type": txn_type,
            "when": when,
            "payer": re.sub(r"\s+", " ", sender.split("\n", 1)[-1]).strip() or sender,
            "phone": (re.findall(r"\d{6,}", sender) or [""])[0],
            "amount": parse_amount(amount),
            "incoming": incoming,
        }
        if when and incoming and status == SUCCESSFUL and txn_type in SALE_TXN_TYPES:
            transactions.append(record)
        else:
            record["excluded_because"] = (
                "unparsable date" if not when else
                f"status {status}" if status != SUCCESSFUL else
                "money out" if not incoming else
                f"type {txn_type}"
            )
            other.append(record)

    transactions.sort(key=lambda t: t["when"])
    meta["excluded"] = other
    return transactions, meta


# ── the sales book (xlsx) ────────────────────────────────────────────────────
def read_book(path: str) -> tuple[list[dict], list[dict], dict]:
    """Group a day's MoMo lines into orders.

    Returns ``(orders, voided_orders, stats)``. An order is one Order Id with
    its MoMo lines summed; voided lines are pulled out into their own list so an
    unrecorded payment can be traced back to an order that was cancelled and
    re-rung.
    """
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if SHEET_NAME not in workbook.sheetnames:
        sys.exit(f"{path}: no {SHEET_NAME!r} sheet (has {workbook.sheetnames}).")
    sheet = workbook[SHEET_NAME]

    rows = sheet.iter_rows(values_only=True)
    try:
        header = [str(c).strip() if c is not None else "" for c in next(rows)]
    except StopIteration:
        sys.exit(f"{path}: {SHEET_NAME!r} is empty.")
    index = {}
    for key, column in BOOK_COLUMNS.items():
        if column not in header:
            sys.exit(f"{path}: {SHEET_NAME!r} has no {column!r} column.")
        index[key] = header.index(column)

    live, voided = OrderedDict(), OrderedDict()
    stats = {"lines": 0, "momo_lines": 0, "voided_lines": 0, "undated_lines": 0}
    for row in rows:
        if row is None or all(c is None for c in row):
            continue
        cell = lambda key: row[index[key]] if index[key] < len(row) else None  # noqa: E731
        stats["lines"] += 1
        if str(cell("method") or "").strip().lower() != MOMO_METHOD:
            continue
        stats["momo_lines"] += 1

        day, clock = parse_book_date(cell("date")), parse_book_time(cell("time"))
        if day is None or clock is None:
            stats["undated_lines"] += 1
            continue

        is_voided = str(cell("status") or "").strip().lower() == VOIDED_STATUS
        if is_voided:
            stats["voided_lines"] += 1
        bucket = voided if is_voided else live
        # Normalised, so a sheet mixing 96 and 96.0 still groups as one order.
        order_id = plain(cell("order"))
        order = bucket.setdefault((day, order_id), {
            "order_id": order_id,
            "label": plain(cell("label")),
            "date": day,
            "when": dt.datetime.combine(day, clock),
            "amount": Decimal("0"),
            "items": [],
            "voided": is_voided,
            "source": os.path.basename(path),
        })
        order["amount"] += parse_amount(cell("total"))
        qty = plain(cell("qty"))
        product = str(cell("product") or "?").strip()
        order["items"].append(f"{product}×{qty}" if qty not in ("", "1") else product)

    workbook.close()      # read_only mode holds the file open until told otherwise
    return list(live.values()), list(voided.values()), stats


# ── matching ─────────────────────────────────────────────────────────────────
def max_matching(edges: list[tuple[tuple, int, int]], left_count: int) -> dict[int, int]:
    """Link as many order/transaction pairs as possible, preferring cheap edges.

    Plain Kuhn augmenting-path matching over the eligible pairs. Each order's
    candidates are tried cheapest first (smallest time gap, then smallest amount
    gap), so the usual case picks the obvious pairing, while the augmenting
    search stops one greedy grab from stranding a neighbouring order that had
    only that single candidate. Returns ``{left index: right index}``.
    """
    candidates: dict[int, list[int]] = defaultdict(list)
    for _cost, left, right in sorted(edges, key=lambda e: e[0]):
        candidates[left].append(right)

    taken_by: dict[int, int] = {}          # right index -> left index

    def augment(left: int, seen: set[int]) -> bool:
        for right in candidates[left]:
            if right in seen:
                continue
            seen.add(right)
            if right not in taken_by or augment(taken_by[right], seen):
                taken_by[right] = left
                return True
        return False

    for left in range(left_count):
        if candidates[left]:
            augment(left, set())
    return {left: right for right, left in taken_by.items()}


def pair_up(orders: list[dict], transactions: list[dict], tolerance: dt.timedelta,
            *, exact_amount: bool) -> dict[int, int]:
    """One matching pass over everything still unpaired."""
    edges = []
    for i, order in enumerate(orders):
        for j, txn in enumerate(transactions):
            gap = abs(txn["when"] - order["when"])
            if gap > tolerance:
                continue
            difference = abs(txn["amount"] - order["amount"])
            if exact_amount and difference:
                continue
            edges.append(((gap, difference), i, j))
    return max_matching(edges, len(orders))


def reconcile_day(orders: list[dict], transactions: list[dict],
                  tolerance: dt.timedelta) -> tuple[list[dict], list[dict], list[dict]]:
    """Match one day. Returns ``(links, unmatched orders, unmatched transactions)``."""
    links = []

    def take(pairs, orders, transactions, kind):
        for i, j in sorted(pairs.items()):
            order, txn = orders[i], transactions[j]
            links.append({
                "kind": kind,
                "order": order,
                "txn": txn,
                "delta_seconds": int((txn["when"] - order["when"]).total_seconds()),
                "delta_amount": txn["amount"] - order["amount"],
            })
        return ([o for i, o in enumerate(orders) if i not in pairs],
                [t for j, t in enumerate(transactions) if j not in set(pairs.values())])

    exact = pair_up(orders, transactions, tolerance, exact_amount=True)
    orders, transactions = take(exact, orders, transactions, "exact")
    loose = pair_up(orders, transactions, tolerance, exact_amount=False)
    orders, transactions = take(loose, orders, transactions, "amount-mismatch")

    links.sort(key=lambda link: link["txn"]["when"])
    return links, orders, transactions


def nearest_same_amount(order: dict, transactions: list[dict]) -> dict | None:
    """The closest leftover transaction for the same money — used to explain an
    unmatched order as "just outside the window" instead of "never paid"."""
    same = [t for t in transactions if t["amount"] == order["amount"]]
    if not same:
        return None
    return min(same, key=lambda t: abs(t["when"] - order["when"]))


def nearest_voided(txn: dict, voided_orders: list[dict], tolerance: dt.timedelta) -> dict | None:
    """A voided order that lines up with an unrecorded payment — the classic
    "rang it up wrong, voided it, re-rang it" case where the money did arrive."""
    near = [o for o in voided_orders
            if abs(o["when"] - txn["when"]) <= tolerance and o["amount"] == txn["amount"]]
    return min(near, key=lambda o: abs(o["when"] - txn["when"])) if near else None


def split_payment_hint(link: dict, unrecorded: list[dict], tolerance: dt.timedelta) -> dict | None:
    """A leftover payment that covers exactly what a matched pair came up short.

    One customer settling an order with two taps is common, and the passes above
    only ever link one payment per order — so the first leg lands as an amount
    mismatch and the second as unrecorded money. Spotting that the two add up
    turns a pair of scary-looking flags into one explained order. This only
    annotates the report; neither row is quietly written off.
    """
    shortfall = -link["delta_amount"]        # positive when the book asked for more
    if shortfall <= 0:
        return None
    order = link["order"]
    near = [entry for entry in unrecorded
            if entry["txn"]["amount"] == shortfall
            and abs(entry["txn"]["when"] - order["when"]) <= tolerance]
    if not near:
        return None
    payer = name_tokens(link["txn"]["payer"])
    same_payer = [e for e in near if payer & name_tokens(e["txn"]["payer"])]
    entry = min(same_payer or near, key=lambda e: abs(e["txn"]["when"] - order["when"]))
    return {"entry": entry, "same_payer": bool(same_payer)}


# ── reporting ────────────────────────────────────────────────────────────────
def order_ref(order: dict) -> str:
    label = f"/{order['label']}" if order["label"] else ""
    return f"order {order['order_id']}{label}"


def txn_tag(txn: dict) -> str:
    """Mark a sale that arrived on something other than a plain MoMo payment,
    so a bank/EKash push isn't silently read as a normal tap."""
    return "" if txn["type"] == PLAIN_TXN_TYPE else f" [{txn['type'].lower()}]"


def print_report(result: dict, args) -> None:
    meta = result["meta"]
    print("=" * 78)
    print("MoMo reconciliation")
    print("=" * 78)
    print(f"Statement : {os.path.basename(meta['path'])}")
    print(f"Account   : {meta['customer']} ({meta['number']})")
    print(f"Period    : {meta['period']}")
    print(f"Books     : {', '.join(result['books']) or '(none)'}")
    print(f"Days      : {', '.join(d.isoformat() for d in result['days']) or '(none)'}")
    print(f"Tolerance : ±{args.tolerance} min on time, exact amount preferred")

    if result["undated_days"]:
        print("\n! Statement has no transactions on: "
              + ", ".join(d.isoformat() for d in result["undated_days"]))

    if args.matched and result["links"]:
        print("\nMatched")
        print("-" * 78)
        for link in result["links"]:
            order, txn = link["order"], link["txn"]
            flag = "✓" if link["kind"] == "exact" else "≈"
            note = "" if link["kind"] == "exact" else f"  Δamt {link['delta_amount']:+,}"
            print(f"  {flag} {order['when']:%Y-%m-%d %H:%M} {order_ref(order):<16} "
                  f"{order['amount']:>8,} ↔ {txn['when']:%H:%M:%S} {txn['amount']:>8,} "
                  f"{txn['payer'][:24]:<24} Δt {link['delta_seconds']:+5}s{note}{txn_tag(txn)}")

    mismatched = [l for l in result["links"] if l["kind"] != "exact"]
    if mismatched:
        print("\nMatched on time but the amounts differ — check these")
        print("-" * 78)
        for link in mismatched:
            order, txn = link["order"], link["txn"]
            print(f"  {order['when']:%Y-%m-%d %H:%M} {order_ref(order):<16} book {order['amount']:>8,} "
                  f"vs paid {txn['amount']:>8,} ({link['delta_amount']:+,}) "
                  f"— {txn['payer'][:24]}, txn {txn['id']}{txn_tag(txn)}")
            print(f"      {', '.join(order['items'])[:70]}")
            hint = link["split_hint"]
            if hint:
                other = hint["entry"]["txn"]
                who = "the same payer" if hint["same_payer"] else other["payer"][:24]
                print(f"      likely a SPLIT PAYMENT: {other['amount']:,} more at "
                      f"{other['when']:%H:%M:%S} from {who} (txn {other['id']}{txn_tag(other)}) "
                      f"covers the difference exactly")

    if result["unmatched_orders"]:
        print("\nBooked as MoMo but no payment found — was it really MoMo?")
        print("-" * 78)
        for entry in result["unmatched_orders"]:
            order = entry["order"]
            print(f"  {order['when']:%Y-%m-%d %H:%M} {order_ref(order):<16} {order['amount']:>8,}"
                  f"  {', '.join(order['items'])[:44]}")
            near = entry["nearest"]
            if near:
                gap = round((near["when"] - order["when"]).total_seconds() / 60)
                where = (f"— re-run with --tolerance {abs(gap) + 1} if that is the one"
                         if abs(gap) <= NEAR_MISS_SUGGEST_MIN
                         else "— too far apart to be the same sale, most likely a different customer")
                print(f"      nearest unmatched payment for the same amount is "
                      f"{gap:+} min away ({near['when']:%H:%M:%S}, {near['payer'][:20]})"
                      f"{txn_tag(near)} {where}")

    print("\nUNRECORDED — money received, no order in the book")
    print("-" * 78)
    if not result["unrecorded"]:
        print("  (none — every payment is accounted for)")
    for entry in result["unrecorded"]:
        txn = entry["txn"]
        print(f"  {txn['when']:%Y-%m-%d %H:%M:%S} {txn['amount']:>8,} "
              f"{txn['payer'][:28]:<28} {txn['phone']:<13} txn {txn['id']}{txn_tag(txn)}")
        if entry["voided_match"]:
            voided = entry["voided_match"]
            print(f"      matches VOIDED {order_ref(voided)} at {voided['when']:%H:%M} "
                  f"— paid, then voided in the book")
        if entry.get("split_of"):
            order = entry["split_of"]["order"]
            print(f"      looks like the second half of {order_ref(order)} at "
                  f"{order['when']:%H:%M} — see the amount-mismatch list above")

    if result["outside_books"]:
        print(f"\nOn the statement but no sales book for that day — {len(result['outside_books'])} "
              f"payment(s), {money(sum(t['amount'] for t in result['outside_books']))}")
        print("-" * 78)
        by_day = defaultdict(lambda: [0, Decimal("0")])
        for txn in result["outside_books"]:
            bucket = by_day[txn["when"].date()]
            bucket[0] += 1
            bucket[1] += txn["amount"]
        for day in sorted(by_day):
            count, total = by_day[day]
            print(f"  {day}  {count:>3} payment(s)  {total:>10,}")
        print("  Add the sales book for these days with --book to reconcile them.")

    totals = result["totals"]
    print("\n" + "=" * 78)
    print("Summary")
    print(f"  book, MoMo orders          : {totals['orders']:>4}   {money(totals['book_momo']):>18}")
    print(f"      matched exactly        : {totals['exact']:>4}   {money(totals['exact_amount']):>18}")
    print(f"      matched, amount differs: {totals['mismatched']:>4}   "
          f"{money(totals['mismatch_booked']):>18}")
    print(f"      booked but unpaid      : {totals['unmatched_orders']:>4}   "
          f"{money(totals['unmatched_order_amount']):>18}")
    print(f"  statement, payments in     : {totals['transactions']:>4}   {money(totals['statement']):>18}")
    print(f"      matched exactly        : {totals['exact']:>4}   {money(totals['exact_amount']):>18}")
    print(f"      matched, amount differs: {totals['mismatched']:>4}   "
          f"{money(totals['mismatch_paid']):>18}")
    print(f"      UNRECORDED             : {totals['unrecorded']:>4}   "
          f"{money(totals['unrecorded_amount']):>18}")
    print(f"  {'-' * 60}")
    print(f"  statement − book           : {' ':>4}   {money(totals['difference']):>18}")
    if totals["transfers"]:
        print(f"\n  Of those payments in, {totals['transfers']} arrived as a transfer "
              f"(bank/EKash push) rather than a MoMo tap — {money(totals['transfer_amount'])}, "
              f"tagged in the lists above.")
    if totals["split_payments"]:
        print(f"\n  {totals['split_payments']} amount mismatch(es) look like split payments — "
              f"the missing money is in the unrecorded list.")
    if totals["excluded"]:
        print(f"\n  Not counted as sales: {totals['excluded']} statement row(s) — "
              + ", ".join(f"{reason} ×{count}" for reason, count
                          in sorted(totals["excluded_reasons"].items())))
    if totals["voided_orders"]:
        print(f"  Voided orders excluded from the book total: {totals['voided_orders']} "
              f"({money(totals['voided_amount'])})")
    if totals["undated_lines"]:
        print(f"  Book lines skipped for a missing/unreadable date or time: {totals['undated_lines']}")


def to_json(result: dict) -> dict:
    def order_out(order):
        return {"order_id": order["order_id"], "label": order["label"],
                "when": order["when"].isoformat(), "amount": str(order["amount"]),
                "items": order["items"], "source": order["source"]}

    def txn_out(txn):
        return {"id": txn["id"], "type": txn["type"], "when": txn["when"].isoformat(),
                "amount": str(txn["amount"]), "payer": txn["payer"], "phone": txn["phone"]}

    return {
        "statement": {k: result["meta"][k] for k in ("path", "customer", "number", "period")},
        "books": result["books"],
        "days": [d.isoformat() for d in result["days"]],
        "tolerance_minutes": result["tolerance_minutes"],
        "matched": [{"kind": l["kind"], "order": order_out(l["order"]), "txn": txn_out(l["txn"]),
                     "delta_seconds": l["delta_seconds"], "delta_amount": str(l["delta_amount"]),
                     "split_payment": (txn_out(l["split_hint"]["entry"]["txn"])
                                       if l.get("split_hint") else None)}
                    for l in result["links"]],
        "unmatched_orders": [{"order": order_out(e["order"]),
                              "nearest_same_amount": txn_out(e["nearest"]) if e["nearest"] else None}
                             for e in result["unmatched_orders"]],
        "unrecorded": [{"txn": txn_out(e["txn"]),
                        "voided_order": order_out(e["voided_match"]) if e["voided_match"] else None,
                        "split_of_order": (order_out(e["split_of"]["order"])
                                           if e.get("split_of") else None)}
                       for e in result["unrecorded"]],
        "outside_books": [txn_out(t) for t in result["outside_books"]],
        "totals": {k: (str(v) if isinstance(v, Decimal) else v)
                   for k, v in result["totals"].items() if k != "excluded_reasons"},
    }


def write_csv(result: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["status", "date", "order_id", "order_label", "order_time",
                         "order_amount", "txn_id", "txn_type", "txn_time", "txn_amount", "payer",
                         "phone", "delta_seconds", "delta_amount", "items", "source"])
        for link in result["links"]:
            order, txn = link["order"], link["txn"]
            writer.writerow([link["kind"], order["date"], order["order_id"], order["label"],
                             f"{order['when']:%H:%M}", order["amount"], txn["id"], txn["type"],
                             f"{txn['when']:%H:%M:%S}", txn["amount"], txn["payer"], txn["phone"],
                             link["delta_seconds"], link["delta_amount"],
                             "; ".join(order["items"]), order["source"]])
        for entry in result["unmatched_orders"]:
            order = entry["order"]
            writer.writerow(["booked-unpaid", order["date"], order["order_id"], order["label"],
                             f"{order['when']:%H:%M}", order["amount"], "", "", "", "", "", "", "",
                             "", "; ".join(order["items"]), order["source"]])
        for entry in result["unrecorded"]:
            txn = entry["txn"]
            note = (f"matches voided order {entry['voided_match']['order_id']}"
                    if entry["voided_match"] else
                    f"likely split payment for order {entry['split_of']['order']['order_id']}"
                    if entry.get("split_of") else "")
            writer.writerow(["unrecorded", txn["when"].date(), "", "", "", "", txn["id"],
                             txn["type"], f"{txn['when']:%H:%M:%S}", txn["amount"], txn["payer"],
                             txn["phone"], "", "", note, ""])
        for txn in result["outside_books"]:
            writer.writerow(["no-book", txn["when"].date(), "", "", "", "", txn["id"], txn["type"],
                             f"{txn['when']:%H:%M:%S}", txn["amount"], txn["payer"], txn["phone"],
                             "", "", "", ""])


# ── orchestration ────────────────────────────────────────────────────────────
def reconcile(statement_path: str, book_paths: list[str], tolerance_minutes: int,
              business: str | None) -> dict:
    transactions, meta = read_statement(statement_path, business)

    orders, voided_orders, book_stats = [], [], defaultdict(int)
    books = []
    for path in book_paths:
        day_orders, day_voided, stats = read_book(path)
        orders += day_orders
        voided_orders += day_voided
        for key, value in stats.items():
            book_stats[key] += value
        books.append(os.path.basename(path))

    tolerance = dt.timedelta(minutes=tolerance_minutes)
    book_days = sorted({o["date"] for o in orders} | {o["date"] for o in voided_orders})

    in_scope, outside = [], []
    for txn in transactions:
        (in_scope if txn["when"].date() in set(book_days) else outside).append(txn)

    by_day_orders = defaultdict(list)
    for order in orders:
        by_day_orders[order["date"]].append(order)
    by_day_txns = defaultdict(list)
    for txn in in_scope:
        by_day_txns[txn["when"].date()].append(txn)

    links, unmatched_orders, unrecorded = [], [], []
    for day in book_days:
        day_links, day_orders_left, day_txns_left = reconcile_day(
            by_day_orders[day], by_day_txns[day], tolerance)
        links += day_links
        unmatched_orders += [{"order": o, "nearest": nearest_same_amount(o, day_txns_left)}
                             for o in day_orders_left]
        unrecorded += [{"txn": t, "voided_match": nearest_voided(t, voided_orders, tolerance)}
                       for t in day_txns_left]

    exact = [l for l in links if l["kind"] == "exact"]
    mismatched = [l for l in links if l["kind"] != "exact"]

    # Cross-reference the two "problem" lists: an underpaid order and a leftover
    # payment that covers the gap are almost always one split payment.
    for link in mismatched:
        hint = split_payment_hint(link, unrecorded, tolerance)
        link["split_hint"] = hint
        if hint:
            hint["entry"]["split_of"] = link

    book_momo = sum((o["amount"] for o in orders), Decimal("0"))
    statement_total = sum((t["amount"] for t in in_scope), Decimal("0"))
    # Sales that came in on another rail. Counted as sales, but worth calling out
    # so a run full of them is noticed rather than assumed to be MoMo taps.
    transfers = [t for t in in_scope if t["type"] != PLAIN_TXN_TYPE]

    excluded_reasons: dict[str, int] = defaultdict(int)
    for row in meta["excluded"]:
        excluded_reasons[row["excluded_because"]] += 1

    return {
        "meta": meta,
        "books": books,
        "days": book_days,
        "undated_days": [d for d in book_days if not by_day_txns[d]],
        "tolerance_minutes": tolerance_minutes,
        "links": sorted(links, key=lambda l: l["txn"]["when"]),
        "unmatched_orders": sorted(unmatched_orders, key=lambda e: e["order"]["when"]),
        "unrecorded": sorted(unrecorded, key=lambda e: e["txn"]["when"]),
        "outside_books": outside,
        "totals": {
            "orders": len(orders),
            "transactions": len(in_scope),
            "exact": len(exact),
            "exact_amount": sum((l["txn"]["amount"] for l in exact), Decimal("0")),
            "mismatched": len(mismatched),
            "mismatch_booked": sum((l["order"]["amount"] for l in mismatched), Decimal("0")),
            "mismatch_paid": sum((l["txn"]["amount"] for l in mismatched), Decimal("0")),
            "mismatch_delta": sum((l["delta_amount"] for l in mismatched), Decimal("0")),
            "split_payments": sum(1 for l in mismatched if l["split_hint"]),
            "unmatched_orders": len(unmatched_orders),
            "unmatched_order_amount": sum((e["order"]["amount"] for e in unmatched_orders),
                                          Decimal("0")),
            "unrecorded": len(unrecorded),
            "unrecorded_amount": sum((e["txn"]["amount"] for e in unrecorded), Decimal("0")),
            "transfers": len(transfers),
            "transfer_amount": sum((t["amount"] for t in transfers), Decimal("0")),
            "book_momo": book_momo,
            "statement": statement_total,
            "difference": statement_total - book_momo,
            "excluded": len(meta["excluded"]),
            "excluded_reasons": dict(excluded_reasons),
            "voided_orders": len(voided_orders),
            "voided_amount": sum((o["amount"] for o in voided_orders), Decimal("0")),
            "undated_lines": book_stats["undated_lines"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile a MoMo statement PDF against the sales book(s) for the same day(s).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--statement", default=DEFAULT_STATEMENT,
                        help="MoMo statement PDF (env MOMO_STATEMENT_PDF).")
    parser.add_argument("--book", nargs="+", default=[DEFAULT_BOOK], metavar="XLSX",
                        help="Sales book(s) to reconcile — one per day (env SALES_XLSX).")
    parser.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE_MIN, metavar="MIN",
                        help=f"How far apart a payment and an order may be, in minutes "
                             f"(default ±{DEFAULT_TOLERANCE_MIN}).")
    parser.add_argument("--business",
                        help="Account holder name/number to treat as 'us' when deciding which "
                             "way the money went. Default: the Customer line on the statement.")
    parser.add_argument("--matched", action="store_true",
                        help="Also list every matched pair, not just the problems.")
    parser.add_argument("--csv", metavar="PATH", help="Write the full reconciliation to a CSV.")
    parser.add_argument("--json", action="store_true",
                        help="Print the result as JSON instead of the report.")
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args()
    for path in [args.statement, *args.book]:
        if not os.path.isfile(path):
            sys.exit(f"File not found: {path}")
    if args.tolerance < 0:
        sys.exit("--tolerance must be zero or more minutes.")

    result = reconcile(args.statement, args.book, args.tolerance, args.business)

    if args.json:
        print(json.dumps(to_json(result), indent=2, ensure_ascii=False))
    else:
        print_report(result, args)
    if args.csv:
        write_csv(result, args.csv)
        if not args.json:
            print(f"\nWrote {args.csv}")

    # Non-zero when something needs a human: unrecorded money, an order that was
    # booked as MoMo but never paid, or a payment that doesn't match its order.
    totals = result["totals"]
    return 1 if (totals["unrecorded"] or totals["unmatched_orders"]
                 or totals["mismatched"]) else 0


if __name__ == "__main__":
    sys.exit(main())
