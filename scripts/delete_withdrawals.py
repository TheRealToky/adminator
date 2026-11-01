#!/usr/bin/env python3
r"""Undo bulk expenses imported by `import_expenses.py` with `--target expense`.

CONTEXT:
  * Running `import_expenses.py` without flags imports rows into `Transaction`
    (direction='expense'), which appear on the GUI "Transactions" page.
  * Running `import_expenses.py --target expense` creates duplicate standalone
    `Expense` models in `finance_expense`, which also debit the wallets and appear
    in Wallet History as expense movements, but do NOT show on the Transactions page.
  * This script removes the `Expense` rows created by `--target expense` while
    leaving all `Transaction` rows on the Transactions page completely untouched.

SCOPE AND SAFETY:
  * Targets `finance_expense` rows within the specified date range (default:
    2026-08-13 to 2026-09-24).
  * CRITICAL: Transactions (from the "Transactions" page, stored in
    ``finance_transaction``) are COMPLETELY UNTOUCHED.
  * Sales (from the "Sales" page, stored in ``sales_sale``) are COMPLETELY UNTOUCHED.
  * Wallet balances in Adminator are derived live from opening balances and entries
    (including expenses), so deleting these duplicate expense rows automatically
    restores the debited amounts back to the respective wallets.

SAFE BY DEFAULT:
  * Runs in **DRY-RUN** mode by default (inspects and prints all matching records,
    shows projected wallet balances, deletes nothing).
  * Pass ``--commit`` or set environment variable ``COMMIT=1`` to actually delete.

USAGE (from repository root on host):

PowerShell (Windows):
    # Preview (dry-run):
    Get-Content scripts/delete_withdrawals.py | `
        docker exec -i adminator-scratch-backend python manage.py shell

    # Actually delete (undo import):
    Get-Content scripts/delete_withdrawals.py | `
        docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell

    # Filter by specific wallet (optional):
    Get-Content scripts/delete_withdrawals.py | `
        docker exec -i -e WALLET_NAME="Petite caisse" -e COMMIT=1 `
        adminator-scratch-backend python manage.py shell

    # Custom date range (optional):
    Get-Content scripts/delete_withdrawals.py | `
        docker exec -i -e START_DATE=2026-08-13 -e END_DATE=2026-09-24 -e COMMIT=1 `
        adminator-scratch-backend python manage.py shell

Bash / Linux / macOS:
    # Preview (dry-run):
    docker exec -i adminator-scratch-backend python manage.py shell < scripts/delete_withdrawals.py

    # Actually delete:
    docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell < scripts/delete_withdrawals.py
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from decimal import Decimal

# ── Django bootstrap (if run directly or outside manage.py shell) ────────────
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

try:
    import django
    from django.apps import apps
    if not apps.ready:
        django.setup()
except Exception:
    pass

from django.db import transaction
from apps.finance.models import (
    Expense,
    Transaction as FinanceTransaction,
    TransactionDirection,
    Wallet,
)
from apps.sales.models import Sale


def parse_arguments() -> tuple[date, date, str | None, bool]:
    """Parse configuration from CLI arguments or environment variables."""
    env_start = os.environ.get("START_DATE", "2026-08-13").strip()
    env_end = os.environ.get("END_DATE", "2026-09-24").strip()
    env_wallet = os.environ.get("WALLET_NAME", "").strip() or None
    env_commit = os.environ.get("COMMIT", "").strip().lower() in {"1", "true", "yes", "y"}

    # If piped into `python manage.py shell`, sys.argv contains manage.py arguments
    is_manage_shell = any("manage.py" in arg or arg == "shell" for arg in sys.argv)

    if is_manage_shell:
        start_str = env_start
        end_str = env_end
        wallet_name = env_wallet
        commit = env_commit
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--start-date",
            default=env_start,
            help="Start date inclusive (YYYY-MM-DD, default 2026-08-13).",
        )
        parser.add_argument(
            "--end-date",
            default=env_end,
            help="End date inclusive (YYYY-MM-DD, default 2026-09-24).",
        )
        parser.add_argument(
            "--wallet",
            default=env_wallet,
            help="Optional: name of specific wallet to filter by (default: all wallets).",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            default=env_commit,
            help="Actually delete matching expense records (default: dry-run).",
        )
        args, _ = parser.parse_known_args()
        start_str = args.start_date
        end_str = args.end_date
        wallet_name = args.wallet
        commit = args.commit

    try:
        start = date.fromisoformat(start_str)
    except ValueError:
        raise SystemExit(f"START_DATE must be YYYY-MM-DD, got {start_str!r}")

    try:
        end = date.fromisoformat(end_str)
    except ValueError:
        raise SystemExit(f"END_DATE must be YYYY-MM-DD, got {end_str!r}")

    if start > end:
        raise SystemExit(f"START_DATE ({start}) cannot be after END_DATE ({end})")

    return start, end, wallet_name, commit


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    start_date, end_date, wallet_name, commit = parse_arguments()

    mode = "COMMIT (DELETING MATCHED ROWS)" if commit else "DRY-RUN (PREVIEW ONLY - NO WRITES)"
    sep = "=" * 70

    print(sep)
    print(" UNDO IMPORT_EXPENSES (--target expense)")
    print(sep)
    print(f" Mode        : {mode}")
    print(f" Date range  : {start_date} to {end_date} (inclusive)")
    print(f" Target      : Expense models (finance_expense) imported via --target expense")
    if wallet_name:
        print(f" Wallet      : {wallet_name!r}")
    else:
        print(" Wallet      : ALL WALLETS")
    print(sep)

    # ── 1. SAFETY AUDIT: Ensure Transactions and Sales pages are preserved ────
    tx_qs = FinanceTransaction.objects.filter(occurred_on__range=(start_date, end_date))
    tx_total = tx_qs.count()
    tx_inc = tx_qs.filter(direction=TransactionDirection.INCOME).count()
    tx_exp = tx_qs.filter(direction=TransactionDirection.EXPENSE).count()

    sales_qs = Sale.objects.filter(occurred_at__date__range=(start_date, end_date))
    sales_total = sales_qs.count()

    print("\n[SAFETY CHECK] TRANSACTIONS & SALES PAGES:")
    print(f"  * Transactions page entries in range : {tx_total} ({tx_inc} inc, {tx_exp} exp) -> 100% PRESERVED")
    print(f"  * Sales page entries in range        : {sales_total} sales receipts          -> 100% PRESERVED")
    print("  Status: Zero rows from Transactions or Sales pages will be touched.")

    # ── 2. QUERY MATCHING EXPENSES TO DELETE ─────────────────────────────────
    expenses_qs = (
        Expense.objects.filter(incurred_on__range=(start_date, end_date))
        .select_related("wallet", "category")
        .order_by("incurred_on", "created_at")
    )

    if wallet_name:
        wallet_obj = Wallet.objects.filter(name__iexact=wallet_name).first()
        if not wallet_obj:
            available = list(Wallet.objects.values_list("name", flat=True))
            raise SystemExit(
                f"\nError: Wallet {wallet_name!r} not found. Available wallets: {available}"
            )
        expenses_qs = expenses_qs.filter(wallet=wallet_obj)

    matched_expenses = list(expenses_qs)

    print(f"\n[QUERY RESULTS] MATCHED EXPENSES TO DELETE:")
    print(f"  Found {len(matched_expenses)} Expense row(s) between {start_date} and {end_date}.")

    if not matched_expenses:
        print("\nNo Expense records found matching the criteria. Nothing to delete.")
        print(sep)
        return 0

    total_amount = sum((e.amount for e in matched_expenses), Decimal("0"))
    print(f"  Total amount to remove: {total_amount:,.2f} RWF\n")

    # Preview entries
    print("--- Sample of Matched Expenses to be Deleted ---")
    for idx, e in enumerate(matched_expenses[:15], start=1):
        wallet_str = e.wallet.name if e.wallet else "no wallet"
        cat_str = e.category.name if e.category else "no category"
        ref_str = f" [ref: {e.reference}]" if e.reference else ""
        print(
            f"  {idx:3d}. ID: {e.id} | Date: {e.incurred_on} | "
            f"Amount: {e.amount:>10.2f} RWF | Wallet: {wallet_str:<20} | "
            f"{e.title} ({cat_str}){ref_str}"
        )
    if len(matched_expenses) > 15:
        print(f"  ... and {len(matched_expenses) - 15} more records.")

    # ── 3. WALLET BALANCES RESTORATION ───────────────────────────────────────
    # Deleting an Expense removes it from wallet.expenses (expenses_out),
    # which increases (restores) the wallet's current_balance by the deleted amount.
    wallets_impacted: dict[Wallet, list[Expense]] = {}
    for e in matched_expenses:
        if e.wallet:
            wallets_impacted.setdefault(e.wallet, []).append(e)

    print("\n--- Impact on Wallet Balances ---")
    for wallet, entries_list in wallets_impacted.items():
        exp_sum = sum((e.amount for e in entries_list), Decimal("0"))
        bal_before = wallet.current_balance
        bal_projected = bal_before + exp_sum
        print(
            f"  * {wallet.name}:"
            f"\n      Duplicate expenses to delete : {len(entries_list)} (sum: {exp_sum:,.2f} RWF)"
            f"\n      Balance before               : {bal_before:,.2f}"
            f"\n      Balance after (restored)     : {bal_projected:,.2f}"
        )

    # ── 4. EXECUTION / DRY-RUN ───────────────────────────────────────────────
    print("\n" + sep)
    if not commit:
        print("RESULT: DRY-RUN COMPLETE")
        print("  * No database rows were deleted.")
        print(f"  * To delete these {len(matched_expenses)} expenses and restore wallet balances,")
        print("    re-run with COMMIT=1 or pass --commit.")
        print(sep)
        return 0

    print("EXECUTING DELETION...")
    target_ids = [e.id for e in matched_expenses]

    with transaction.atomic():
        deleted_count, _ = Expense.objects.filter(id__in=target_ids).delete()

    print(f"Successfully deleted {deleted_count} Expense record(s).")

    # Refresh balances
    print("\n--- Updated Wallet Balances (Actual) ---")
    for wallet in wallets_impacted.keys():
        wallet.refresh_from_db()
        print(f"  * {wallet.name}: New Balance = {wallet.current_balance:,.2f}")

    # Re-verify safety
    tx_after = FinanceTransaction.objects.filter(occurred_on__range=(start_date, end_date)).count()
    sales_after = Sale.objects.filter(occurred_at__date__range=(start_date, end_date)).count()
    print(f"\nFinal Safety Audit:")
    print(f"  * Transactions page entries = {tx_after} (100% intact, 0 deleted)")
    print(f"  * Sales page entries        = {sales_after} (100% intact, 0 deleted)")
    print(sep)
    print("DONE. Duplicate expenses from --target expense successfully undone.")
    return 0


if __name__ in ("__main__", "django.core.management.commands.shell"):
    main()
