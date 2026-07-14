"""Post the cutover opening-balance entry (Phase 2).

Snapshots on-hand inventory value and each wallet's opening balance as at a
cutover date and books them against Opening Balance Equity, so the balance sheet
starts from a real financial position rather than zero.

    python manage.py post_opening_balances --as-of 2026-07-01

This is deliberately conservative: it books inventory (raw + processed +
finished) and wallet opening balances. Receivables from open invoices and fixed
assets can be layered on the same entry once those posting rules land.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.services import inventory_on_hand_value
from apps.finance.models import Wallet
from apps.ledger import chart_of_accounts as coa
from apps.ledger.posting import Leg, post_source

ZERO = Decimal("0")


class Command(BaseCommand):
    help = "Post opening balances (inventory + wallets) against opening-balance equity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of", type=str, default=None,
            help="Cutover date YYYY-MM-DD (default: first of the current month).",
        )

    def handle(self, *args, **options):
        coa.seed_chart_of_accounts()

        raw = options["as_of"]
        if raw:
            try:
                as_of = date.fromisoformat(raw)
            except ValueError as exc:
                raise CommandError(f"Invalid --as-of date: {raw}") from exc
        else:
            today = timezone.localdate()
            as_of = today.replace(day=1)

        legs: list[Leg] = []

        # Inventory on hand, valued at current per-unit costs.
        inv = inventory_on_hand_value()
        finished = Decimal(inv["finished_goods_value"])
        raw_val = Decimal(inv["raw_materials_value"])
        if finished > ZERO:
            legs.append(Leg.dr(coa.account(coa.INVENTORY_FINISHED), finished,
                               memo="Opening finished goods"))
        if raw_val > ZERO:
            legs.append(Leg.dr(coa.account(coa.INVENTORY_RAW), raw_val,
                               memo="Opening raw materials"))

        # Wallet opening balances → their cash sub-accounts.
        for wallet in Wallet.objects.all():
            bal = Decimal(wallet.opening_balance or ZERO)
            if bal == ZERO:
                continue
            acc = coa.cash_account_for_wallet(wallet)
            if bal > ZERO:
                legs.append(Leg.dr(acc, bal, memo=f"Opening cash · {wallet.name}",
                                   wallet=wallet))
            else:
                legs.append(Leg.cr(acc, -bal, memo=f"Opening cash · {wallet.name}",
                                   wallet=wallet))

        if not legs:
            self.stdout.write(self.style.WARNING("Nothing to post — no balances found."))
            return

        # Balance the entry against opening-balance equity.
        net = sum((l.debit - l.credit for l in legs), ZERO)
        equity = coa.account(coa.OPENING_BALANCE_EQUITY)
        if net > ZERO:
            legs.append(Leg.cr(equity, net, memo="Opening balance equity"))
        elif net < ZERO:
            legs.append(Leg.dr(equity, -net, memo="Opening balance equity"))

        entry = post_source(
            source_type="ledger.OpeningBalance", source_id=as_of.isoformat(),
            event="opening", date=as_of, legs=legs,
            memo=f"Opening balances as at {as_of.isoformat()}",
        )
        self.stdout.write(self.style.SUCCESS(
            f"Posted opening balances as at {as_of} "
            f"({entry.lines.count()} legs, total {entry.total_debit})."
        ))
