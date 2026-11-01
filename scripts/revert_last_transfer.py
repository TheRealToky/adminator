#!/usr/bin/env python3
r"""Revert the most recent *transfer* between two wallets.

Defaults to the last transfer **from "Petite caisse" to "Grosse caisse"**.

A transfer is stored as two linked ``WalletEntry`` rows sharing a
``transfer_group`` UUID (see ``WalletTransferSerializer``):

* a ``transfer_out`` on the source wallet (``counterparty_wallet`` = destination),
* a ``transfer_in``  on the destination wallet (``counterparty_wallet`` = source).

"Last transfer" = the ``transfer_out`` on the source wallet whose
``counterparty_wallet`` is the destination, with the latest ``occurred_on`` then
latest ``created_at`` (the same ordering the Wallets page history shows first).
Reverting deletes **both legs** (every row sharing that ``transfer_group``) so
neither wallet is left holding a half-transfer. Deposits, withdrawals, and the
money flows from sales/expenses/transactions live in other rows/tables and are
never touched.

There is no REST endpoint for this — ``WalletEntryViewSet`` is read-only and the
``WalletViewSet`` only *creates* movements — so this talks to the Django ORM
directly and must run **inside the backend container** via ``manage.py shell``.

Wallet balances are derived live, so deleting the rows updates both balances with
no further bookkeeping.

Safe by default: **dry-run** (finds and prints the rows, deletes nothing). Set
``COMMIT=1`` to actually delete.

Usage (from the repo root, on the host).

PowerShell (Windows) — the '<' redirect is a parser error there, so pipe instead:
    # preview what would be reverted
    Get-Content scripts/revert_last_transfer.py | `
        docker exec -i adminator-scratch-backend python manage.py shell

    # actually revert it
    Get-Content scripts/revert_last_transfer.py | `
        docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell

    # a different direction
    Get-Content scripts/revert_last_transfer.py | `
        docker exec -i -e SOURCE_NAME="Grosse caisse" -e DEST_NAME="Petite caisse" -e COMMIT=1 `
        adminator-scratch-backend python manage.py shell

bash/sh:
    docker exec -i adminator-scratch-backend python manage.py shell < scripts/revert_last_transfer.py
    docker exec -i -e COMMIT=1 adminator-scratch-backend python manage.py shell < scripts/revert_last_transfer.py
"""
import os

from django.db import transaction

from apps.finance.models import Wallet, WalletEntry, WalletEntryType

SOURCE_NAME = os.environ.get("SOURCE_NAME", "Petite caisse")
DEST_NAME = os.environ.get("DEST_NAME", "Grosse caisse")
COMMIT = os.environ.get("COMMIT", "").strip().lower() in {"1", "true", "yes", "y"}

mode = "COMMIT" if COMMIT else "DRY-RUN (nothing deleted)"
print(f"Revert last transfer · {mode}")
print(f"From {SOURCE_NAME!r} → {DEST_NAME!r}\n")


# Match wallets case-insensitively so "petite caisse" works too.
def get_wallet(name: str) -> Wallet:
    wallet = Wallet.objects.filter(name__iexact=name).first()
    if wallet is None:
        have = list(Wallet.objects.values_list("name", flat=True))
        raise SystemExit(f"Wallet {name!r} not found. Have: {have}")
    return wallet


source = get_wallet(SOURCE_NAME)
dest = get_wallet(DEST_NAME)
if source.pk == dest.pk:
    raise SystemExit("Source and destination are the same wallet — nothing to revert.")

print(f"Balance before · {source.name}: {source.current_balance}")
print(f"Balance before · {dest.name}:   {dest.current_balance}\n")

# The out-leg on the source, pointing at the destination. Newest first —
# same ordering as WalletEntry.Meta.ordering.
out_leg = (
    WalletEntry.objects.filter(
        wallet=source,
        entry_type=WalletEntryType.TRANSFER_OUT,
        counterparty_wallet=dest,
    )
    .order_by("-occurred_on", "-created_at")
    .first()
)
if out_leg is None:
    raise SystemExit(
        f"No transfer from {source.name!r} to {dest.name!r} found — nothing to revert."
    )

# Both legs share the transfer_group. Fall back to just the out-leg if the group
# is somehow unset (shouldn't happen for transfers created via the API).
if out_leg.transfer_group is not None:
    legs = list(
        WalletEntry.objects.filter(transfer_group=out_leg.transfer_group).order_by(
            "entry_type"
        )
    )
else:
    print("Warning: this transfer_out has no transfer_group; its paired "
          "transfer_in cannot be located, so only the out-leg will be removed.\n")
    legs = [out_leg]

print(f"Reverting transfer (group {out_leg.transfer_group}), {len(legs)} leg(s):\n")
for e in legs:
    print(
        f"  id          : {e.id}\n"
        f"  wallet       : {e.wallet.name}\n"
        f"  entry_type  : {e.entry_type}\n"
        f"  amount      : {e.amount}\n"
        f"  occurred_on : {e.occurred_on}\n"
        f"  created_at  : {e.created_at}\n"
        f"  counterparty: {e.counterparty_wallet.name if e.counterparty_wallet else '—'}\n"
        f"  description : {e.description or '—'}\n"
        f"  reference   : {e.reference or '—'}\n"
    )

if len(legs) != 2:
    print(f"Note: expected 2 legs for a transfer, found {len(legs)}. "
          "Review the rows above before committing.\n")

if COMMIT:
    with transaction.atomic():
        deleted, _ = WalletEntry.objects.filter(id__in=[e.id for e in legs]).delete()
    # current_balance is derived live, so re-read after the delete.
    source.refresh_from_db()
    dest.refresh_from_db()
    print(f"Deleted {deleted} row(s).")
    print(f"Balance after · {source.name}: {source.current_balance}")
    print(f"Balance after · {dest.name}:   {dest.current_balance}")
else:
    print("DRY-RUN — transfer left in place. Re-run with COMMIT=1 to revert it.")
