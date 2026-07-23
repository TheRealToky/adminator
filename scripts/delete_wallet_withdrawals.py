#!/usr/bin/env python3
r"""Delete every *withdrawal* WalletEntry from one wallet on one day.

Defaults to the withdrawals booked against **Grosse caisse** on **2026-07-15**.

There is no REST endpoint for this — ``WalletEntryViewSet`` is read-only and the
``WalletViewSet`` only *creates* movements (deposit/withdraw/transfer). So this
script talks to the Django ORM directly and must run **inside the backend
container** by piping it into ``manage.py shell``.

Scope — only rows with ``entry_type='withdrawal'`` are considered:

* ``transfer_out`` rows are **left alone** even though they also debit the
  wallet. A transfer is two linked rows sharing a ``transfer_group``; deleting
  just this side would leave the destination wallet holding money that never
  left anywhere. Untangle those by hand if you really mean to.
* Deposits, transfers, and the money flows from sales/expenses/transactions are
  never touched — they live in other tables.

``occurred_on`` is a plain local ``DateField``, so the day is compared directly
with no timezone conversion (unlike sales, which are timestamptz).

Wallet balances are derived live, so deleting the rows updates the balance with
no further bookkeeping.

Safe by default: **dry-run** (finds and prints the rows, deletes nothing). Set
``COMMIT=1`` to actually delete.

Usage (from the repo root, on the host).

PowerShell (Windows) — the '<' redirect is a parser error there, so pipe instead:
    # preview what would be deleted
    Get-Content scripts/delete_wallet_withdrawals.py | `
        docker exec -i adminator-scratch-backend python manage.py shell

    # actually delete them
    Get-Content scripts/delete_wallet_withdrawals.py | `
        docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell

    # a different wallet / day
    Get-Content scripts/delete_wallet_withdrawals.py | `
        docker exec -i -e WALLET_NAME="Petite caisse" -e DAY=2026-07-01 -e COMMIT=1 `
        adminator-scratch-backend python manage.py shell

bash/sh:
    docker exec -i adminator-scratch-backend python manage.py shell < scripts/delete_wallet_withdrawals.py
    docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell < scripts/delete_wallet_withdrawals.py
"""
import os
from datetime import date

from django.db import transaction

from apps.finance.models import Wallet, WalletEntry, WalletEntryType

WALLET_NAME = os.environ.get("WALLET_NAME", "Grosse caisse")
DAY = os.environ.get("DAY", "2026-07-15")
COMMIT = os.environ.get("COMMIT", "").strip().lower() in {"1", "true", "yes", "y"}

try:
    day = date.fromisoformat(DAY)
except ValueError:
    raise SystemExit(f"DAY must be YYYY-MM-DD, got {DAY!r}")

mode = "COMMIT" if COMMIT else "DRY-RUN (nothing deleted)"
print(f"Delete wallet withdrawals · {mode}")
print(f"Wallet: {WALLET_NAME!r}   Day: {day}\n")

# Match the wallet case-insensitively so "grosse caisse" works too.
wallet = Wallet.objects.filter(name__iexact=WALLET_NAME).first()
if wallet is None:
    have = list(Wallet.objects.values_list("name", flat=True))
    raise SystemExit(f"Wallet {WALLET_NAME!r} not found. Have: {have}")

print(f"Balance before: {wallet.current_balance}")

entries = list(
    WalletEntry.objects.filter(
        wallet=wallet,
        entry_type=WalletEntryType.WITHDRAWAL,
        occurred_on=day,
    ).order_by("created_at")
)
if not entries:
    raise SystemExit(
        f"No withdrawals on {wallet.name!r} for {day} — nothing to delete."
    )

total = sum(e.amount for e in entries)
print(f"\nMatched {len(entries)} withdrawal(s), totalling {total}:\n")
for e in entries:
    print(
        f"  id          : {e.id}\n"
        f"  amount      : {e.amount}\n"
        f"  created_at  : {e.created_at}\n"
        f"  description : {e.description or '—'}\n"
        f"  reference   : {e.reference or '—'}\n"
    )

# Flag anything else that debits the wallet that day but is deliberately out of
# scope, so a surprising balance afterwards is explainable.
transfers_out = WalletEntry.objects.filter(
    wallet=wallet,
    entry_type=WalletEntryType.TRANSFER_OUT,
    occurred_on=day,
).count()
if transfers_out:
    print(
        f"Note: {transfers_out} transfer_out row(s) on this wallet that day are "
        "NOT included (deleting one leg of a transfer would break the pair).\n"
    )

if COMMIT:
    with transaction.atomic():
        deleted, _ = WalletEntry.objects.filter(
            id__in=[e.id for e in entries]
        ).delete()
    # current_balance is derived live, so re-read it after the delete.
    wallet.refresh_from_db()
    print(f"Deleted {deleted} row(s). Balance after: {wallet.current_balance}")
else:
    print("DRY-RUN — withdrawals left in place. Re-run with COMMIT=1 to delete them.")
