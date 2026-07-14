"""Post straight-line depreciation for a month (Phase 4).

For every active, depreciating :class:`Asset`, book one month of straight-line
depreciation into the GL:

    Dr Depreciation expense (5300) ; Cr Accumulated depreciation (1590)

Idempotent — each charge is keyed on ``(Asset, month)``, so re-running the job
for the same month never double-charges. Run it monthly (e.g. from cron):

    python manage.py post_depreciation                 # current month
    python manage.py post_depreciation --month 2026-06 # a specific month
    python manage.py post_depreciation --catch-up      # every month to date

``--catch-up`` posts every month from each asset's purchase up to the target
month, which is handy when bootstrapping the ledger on existing assets.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.finance.models import Asset, AssetStatus
from apps.ledger import chart_of_accounts as coa
from apps.ledger import posting_rules

ZERO = Decimal("0")


def _months_between(start: date, end: date):
    """Yield the first-of-month for every month in [start, end] inclusive."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield date(y, m, 1)
        m += 1
        if m > 12:
            m, y = 1, y + 1


class Command(BaseCommand):
    help = "Post monthly straight-line depreciation for all depreciating assets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month", type=str, default=None,
            help="Target month YYYY-MM (default: current month).",
        )
        parser.add_argument(
            "--catch-up", action="store_true",
            help="Post every month from each asset's purchase up to the target.",
        )

    def handle(self, *args, **options):
        coa.seed_chart_of_accounts()

        raw = options["month"]
        if raw:
            try:
                target = date.fromisoformat(f"{raw}-01")
            except ValueError as exc:
                raise CommandError(f"Invalid --month (want YYYY-MM): {raw}") from exc
        else:
            target = timezone.localdate().replace(day=1)

        assets = Asset.objects.filter(
            status=AssetStatus.ACTIVE, useful_life_months__isnull=False
        )
        charges = 0
        for asset in assets:
            months = (
                _months_between(asset.purchase_date.replace(day=1), target)
                if options["catch_up"]
                else [target]
            )
            for month in months:
                if posting_rules.depreciation_for_month(asset, month) > ZERO:
                    posting_rules.post_depreciation(asset, month)
                    charges += 1

        self.stdout.write(self.style.SUCCESS(
            f"Posted depreciation: {charges} monthly charge(s) across "
            f"{assets.count()} asset(s) through {target:%Y-%m}."
        ))
