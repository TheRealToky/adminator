"""Create the starter chart of accounts. Idempotent — safe to run repeatedly."""
from django.core.management.base import BaseCommand

from apps.ledger.chart_of_accounts import seed_chart_of_accounts


class Command(BaseCommand):
    help = "Seed the chart of accounts (idempotent)."

    def handle(self, *args, **options):
        created = seed_chart_of_accounts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Chart of accounts ready ({created} account(s) created)."
            )
        )
