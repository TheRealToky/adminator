#!/usr/bin/env python3
r"""Delete the most recent *deposit* WalletEntry from a wallet (default: Petite caisse).

There is no REST endpoint for this — ``WalletEntryViewSet`` is read-only and the
``WalletViewSet`` only *creates* movements (deposit/withdraw/transfer). So this
script talks to the Django ORM directly and must run **inside the backend
container** by piping it into ``manage.py shell``.

"Last deposit" = the deposit with the latest ``occurred_on`` then latest
``created_at`` (the same ordering the Wallets page history shows first). Only
rows with ``entry_type='deposit'`` are considered — withdrawals, transfers, and
the money flows from sales/expenses/transactions are never touched.

Safe by default: **dry-run** (finds and prints the row, deletes nothing). Set
``COMMIT=1`` to actually delete. Override the wallet with ``WALLET_NAME``.

Usage (from the repo root, on the host):
    # preview what would be deleted
    docker exec -i adminator-scratch-backend python manage.py shell < scripts/delete_last_deposit.py

    # actually delete it
    docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell < scripts/delete_last_deposit.py

    # a different wallet
    docker exec -i -e WALLET_NAME="Bank" -e COMMIT=1 adminator-scratch-backend python manage.py shell < scripts/delete_last_deposit.py
"""
import os

from apps.finance.models import Wallet, WalletEntry, WalletEntryType

WALLET_NAME = os.environ.get("WALLET_NAME", "Petite caisse")
COMMIT = os.environ.get("COMMIT", "").strip().lower() in {"1", "true", "yes", "y"}

mode = "COMMIT" if COMMIT else "DRY-RUN (nothing deleted)"
print(f"Delete last deposit · {mode}")
print(f"Wallet: {WALLET_NAME!r}\n")

# Match the wallet case-insensitively so "petite caisse" works too.
wallet = Wallet.objects.filter(name__iexact=WALLET_NAME).first()
if wallet is None:
    have = list(Wallet.objects.values_list("name", flat=True))
    raise SystemExit(f"Wallet {WALLET_NAME!r} not found. Have: {have}")

print(f"Balance before: {wallet.current_balance}")

# Newest deposit first — same ordering as WalletEntry.Meta.ordering.
entry = (
    WalletEntry.objects.filter(wallet=wallet, entry_type=WalletEntryType.DEPOSIT)
    .order_by("-occurred_on", "-created_at")
    .first()
)
if entry is None:
    raise SystemExit(f"No deposit entries on wallet {wallet.name!r} — nothing to delete.")

print(
    "Last deposit:\n"
    f"  id          : {entry.id}\n"
    f"  amount      : {entry.amount}\n"
    f"  occurred_on : {entry.occurred_on}\n"
    f"  created_at  : {entry.created_at}\n"
    f"  description : {entry.description or '—'}\n"
    f"  reference   : {entry.reference or '—'}\n"
)

if COMMIT:
    entry.delete()
    # current_balance is derived live, so re-read it after the delete.
    wallet.refresh_from_db()
    print(f"Deleted. Balance after: {wallet.current_balance}")
else:
    print("DRY-RUN — deposit left in place. Re-run with COMMIT=1 to delete it.")
