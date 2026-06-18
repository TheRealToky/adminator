#!/usr/bin/env python3
"""Standalone audit: do sales settle into the right kind of wallet?

Connects DIRECTLY to the scratch Postgres (default: localhost:5433, db
``adminator``) over the host-published port — no Django, no exec into the
backend container, no reliance on mounted code. Just a host script + a driver.

Business rule under audit (scoped to two methods for now):

    Mobile Money payment  ->  wallet.account_type == "mobile_money"
    Card payment          ->  wallet.account_type == "bank"

A sale is flagged when it has no wallet linked, or its wallet is the wrong
type. Cash / bank-transfer / credit sales are ignored.

The audit always runs over a precise, half-open window [start, end) on
``occurred_at``: start included, end excluded. Naive inputs are read in the
business timezone (default Africa/Kigali).

Requirements (host):
    pip install "psycopg[binary]" tzdata

Examples
--------
    python scripts/audit_sale_wallets.py --start 2026-01-01 --end 2026-07-01
    python scripts/audit_sale_wallets.py --start "2026-06-13 00:00" --end "2026-06-14 00:00" --method card
    python scripts/audit_sale_wallets.py --last-days 30 --show-ok
    # point at a different stack:
    python scripts/audit_sale_wallets.py --last-days 7 --port 5432 --password "$env:PGPASSWORD"

Exit status is 1 when any mismatch is found (0 otherwise), so it can be
wired into a scheduled job or CI check.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import psycopg
except ModuleNotFoundError:
    sys.exit(
        "psycopg is not installed on this host.\n"
        '  Fix: python -m pip install "psycopg[binary]" tzdata'
    )

# The rule under audit: payment method -> the wallet account_type it should
# settle into. Deliberately limited to the two methods asked for; extend this
# dict (and METHOD_CHOICES) to cover cash / bank_transfer later.
EXPECTED_WALLET_TYPE = {
    "mobile_money": "mobile_money",
    "card": "bank",
    "cash": "cash",
}
METHOD_LABEL = {"mobile_money": "Mobile Money", "card": "Card", "cash": "Cash"}
WALLET_TYPE_LABEL = {"mobile_money": "Mobile Money", "bank": "Bank Account", "cash": "Petite caisse"}

# Connection defaults point at the scratch stack's host-published port.
CONN_DEFAULTS = {
    "host": "localhost",
    "port": "5433",
    "dbname": "adminator",
    "user": "adminator",
    # Scratch dev placeholder (matches .env.scratch); override with --password.
    "password": os.environ.get("PGPASSWORD", "change-me-in-production"),
}
DEFAULT_TZ = "Africa/Kigali"


# ── argument parsing ────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audit that mobile-money/card sales point at the right wallet type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    win = p.add_argument_group("time window (required: --start/--end or --last-days)")
    win.add_argument("--start", help="Window start, inclusive. 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]'.")
    win.add_argument("--end", help="Window end, exclusive. Same formats as --start.")
    win.add_argument("--last-days", type=int, help="Convenience: the last N days up to now.")

    p.add_argument("--method", choices=sorted(EXPECTED_WALLET_TYPE), help="Audit only this method (default: both).")
    p.add_argument("--tz", default=DEFAULT_TZ, help=f"Timezone for naive inputs and display (default {DEFAULT_TZ}).")
    p.add_argument("--show-ok", action="store_true", help="Also list the sales that pass.")
    p.add_argument("--limit", type=int, default=100, help="Max detail rows per section (0 = no limit). Default 100.")

    conn = p.add_argument_group("connection (defaults target the scratch stack)")
    conn.add_argument("--host", default=CONN_DEFAULTS["host"])
    conn.add_argument("--port", default=CONN_DEFAULTS["port"])
    conn.add_argument("--dbname", default=CONN_DEFAULTS["dbname"])
    conn.add_argument("--user", default=CONN_DEFAULTS["user"])
    conn.add_argument("--password", default=CONN_DEFAULTS["password"])
    return p


def parse_bound(value: str, tz: ZoneInfo, *, label: str) -> datetime:
    dt: datetime | None = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        try:
            d = date.fromisoformat(value)
            dt = datetime(d.year, d.month, d.day)
        except ValueError:
            raise SystemExit(
                f"Could not parse --{label} '{value}'. "
                "Use 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]'."
            )
    return dt.replace(tzinfo=tz)


def resolve_window(args, tz: ZoneInfo) -> tuple[datetime, datetime]:
    if args.start or args.end:
        if not (args.start and args.end):
            raise SystemExit("Provide both --start and --end (or use --last-days).")
        start = parse_bound(args.start, tz, label="start")
        end = parse_bound(args.end, tz, label="end")
    elif args.last_days is not None:
        if args.last_days <= 0:
            raise SystemExit("--last-days must be a positive integer.")
        end = datetime.now(tz)
        start = end - timedelta(days=args.last_days)
    else:
        raise SystemExit("Specify the time window: --start/--end, or --last-days N.")
    if end <= start:
        raise SystemExit("--end must be after --start.")
    return start, end


# ── audit ─────────────────────────────────────────────────────────────--
def fetch_sales(args, start: datetime, end: datetime, methods: list[str]) -> list[dict]:
    sql = """
        SELECT s.receipt_number, s.occurred_at, s.payment_method, s.total,
               w.name AS wallet_name, w.account_type AS wallet_type
        FROM sales_sale s
        LEFT JOIN finance_wallet w ON w.id = s.wallet_id
        WHERE s.occurred_at >= %(start)s
          AND s.occurred_at <  %(end)s
          AND s.payment_method = ANY(%(methods)s)
        ORDER BY s.occurred_at
    """
    params = {"start": start, "end": end, "methods": methods}
    try:
        with psycopg.connect(
            host=args.host, port=args.port, dbname=args.dbname,
            user=args.user, password=args.password, connect_timeout=8,
        ) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
    except psycopg.OperationalError as exc:
        raise SystemExit(
            f"Could not connect to Postgres at {args.host}:{args.port}/{args.dbname}.\n"
            f"  {str(exc).strip()}\n"
            "  Is the scratch stack up?  docker compose -f docker-compose.yml "
            "-f docker-compose.scratch.yml up -d postgres"
        )


def classify(row: dict) -> tuple[bool, str]:
    expected = EXPECTED_WALLET_TYPE[row["payment_method"]]
    if row["wallet_type"] is None:
        return False, "no wallet linked"
    if row["wallet_type"] != expected:
        return False, f"linked to '{row['wallet_name']}' [{row['wallet_type']}], expected [{expected}]"
    return True, ""


# ── output ────────────────────────────────────────────────────────────--
def fmt_dt(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def money(value: Decimal) -> str:
    return f"{value:,.2f}"


def print_summary(stats: dict) -> None:
    print("Summary")
    print(f"  {'method':<14}{'checked':>9}{'ok':>7}{'mismatch':>11}")
    total = {"checked": 0, "ok": 0, "bad": 0}
    for method, s in stats.items():
        for k in total:
            total[k] += s[k]
        print(f"  {method:<14}{s['checked']:>9}{s['ok']:>7}{s['bad']:>11}")
    print(f"  {'-' * 39}")
    print(f"  {'TOTAL':<14}{total['checked']:>9}{total['ok']:>7}{total['bad']:>11}")


def print_rows(title: str, rows: list, tz: ZoneInfo, limit: int, *, mismatch: bool) -> None:
    if not rows:
        return
    last_col = "ISSUE" if mismatch else "WALLET"
    print(f"\n{title} ({len(rows)})")
    print(f"  {'RECEIPT':<18}{'OCCURRED':<18}{'METHOD':<14}{'TOTAL':>13}  {last_col}")
    shown = rows if limit == 0 else rows[:limit]
    for row, tail in shown:
        print(
            f"  {row['receipt_number']:<18}{fmt_dt(row['occurred_at'], tz):<18}"
            f"{row['payment_method']:<14}{money(row['total']):>13}  {tail}"
        )
    if limit and len(rows) > limit:
        print(f"  … {len(rows) - limit} more (raise --limit to see all)")


# ── main ──────────────────────────────────────────────────────────────--
def main() -> int:
    # Windows consoles default to cp1252, which can't encode the report's
    # arrows/bullets/✓. Emit UTF-8 so it never crashes on the box it audits.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args()
    try:
        tz = ZoneInfo(args.tz)
    except ZoneInfoNotFoundError:
        return int(bool(print(f"Unknown timezone '{args.tz}'. Is 'tzdata' installed?"))) or 2

    start, end = resolve_window(args, tz)
    methods = [args.method] if args.method else sorted(EXPECTED_WALLET_TYPE)

    print("Sale → wallet payment-method audit")
    print(f"Target : {args.user}@{args.host}:{args.port}/{args.dbname}")
    print(f"Window : {fmt_dt(start, tz)} → {fmt_dt(end, tz)}  [{args.tz}]  (half-open: start included, end excluded)")
    print("Rule   : " + "  ·  ".join(
        f"{METHOD_LABEL[m]} → {WALLET_TYPE_LABEL[EXPECTED_WALLET_TYPE[m]]} wallet" for m in methods
    ))
    print()

    rows = fetch_sales(args, start, end, methods)

    stats = {m: {"checked": 0, "ok": 0, "bad": 0} for m in methods}
    mismatches: list[tuple[dict, str]] = []
    passing: list[tuple[dict, str]] = []
    for row in rows:
        stats[row["payment_method"]]["checked"] += 1
        ok, reason = classify(row)
        if ok:
            stats[row["payment_method"]]["ok"] += 1
            wallet = f"{row['wallet_name']} [{row['wallet_type']}]"
            passing.append((row, wallet))
        else:
            stats[row["payment_method"]]["bad"] += 1
            mismatches.append((row, reason))

    print_summary(stats)
    if args.show_ok:
        print_rows("Passing sales", passing, tz, args.limit, mismatch=False)
    print_rows("Mismatches", mismatches, tz, args.limit, mismatch=True)

    total_bad = len(mismatches)
    if total_bad:
        print(f"\n✗ {total_bad} sale(s) point at the wrong wallet.")
        return 1
    print("\n✓ Every audited sale is in the right wallet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
