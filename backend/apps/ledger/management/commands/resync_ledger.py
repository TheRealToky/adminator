"""Backfill / re-sync: (re)post ledger entries for every existing domain row.

Idempotent — each source's entry is replaced, not duplicated. Use this to
bootstrap the GL on a database that already had sales/expenses/transactions
before the ledger existed, or to repair drift.

    python manage.py resync_ledger
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import Expense, Invoice, Transaction
from apps.inventory.models import StockMovement
from apps.ledger import posting_rules
from apps.ledger.chart_of_accounts import seed_chart_of_accounts
from apps.processed_materials.models import (
    ProcessedMaterialBatch,
    ProcessedMaterialStockMovement,
)
from apps.production.models import ProductionRun
from apps.sales.models import Sale


class Command(BaseCommand):
    help = "(Re)post ledger entries for all existing domain rows (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet", action="store_true", help="Suppress per-model counts."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        seed_chart_of_accounts()

        sales = Sale.objects.all()
        for sale in sales.iterator():
            posting_rules.post_sale(sale)

        expenses = Expense.objects.select_related("category").all()
        for expense in expenses.iterator():
            posting_rules.post_expense(expense)

        txns = Transaction.objects.all()
        for txn in txns.iterator():
            posting_rules.post_transaction(txn)

        invoices = Invoice.objects.all()
        for invoice in invoices.iterator():
            posting_rules.post_invoice(invoice)

        # Inventory value: stand-alone movements + capitalised production.
        movements = StockMovement.objects.select_related(
            "stock_item__product", "stock_item__raw_material"
        ).all()
        for movement in movements.iterator():
            posting_rules.post_stock_movement(movement)

        pm_movements = ProcessedMaterialStockMovement.objects.select_related(
            "stock__processed_material"
        ).all()
        for movement in pm_movements.iterator():
            posting_rules.post_pm_stock_movement(movement)

        runs = ProductionRun.objects.select_related("product").all()
        for run in runs.iterator():
            posting_rules.post_production_run(run)

        batches = ProcessedMaterialBatch.objects.select_related("processed_material").all()
        for batch in batches.iterator():
            posting_rules.post_processed_batch(batch)

        if not options["quiet"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Re-synced ledger: {sales.count()} sales, "
                    f"{expenses.count()} expenses, {txns.count()} transactions, "
                    f"{invoices.count()} invoices, {movements.count()} stock moves, "
                    f"{pm_movements.count()} processed moves, {runs.count()} runs, "
                    f"{batches.count()} batches."
                )
            )
