"""Connect domain writes to the ledger (shadow mode).

Using signals — rather than editing each service call site — means every write
path (API, admin, seed scripts, bulk imports) posts to the GL uniformly. All
posting is funnelled through the ``safe_*`` wrappers, so a ledger error can
never roll back an operational write while shadow mode is on.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.finance.models import Expense, Invoice, Transaction
from apps.inventory.models import StockMovement
from apps.processed_materials.models import (
    ProcessedMaterialBatch,
    ProcessedMaterialStockMovement,
)
from apps.production.models import ProductionRun
from apps.sales.models import Sale

from . import posting_rules


# ── Sale ─────────────────────────────────────────────────────────────────────
@receiver(post_save, sender=Sale, dispatch_uid="ledger_post_sale")
def _on_sale_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_sale(instance)


@receiver(post_delete, sender=Sale, dispatch_uid="ledger_reverse_sale")
def _on_sale_deleted(sender, instance, **kwargs):
    posting_rules.reverse_sale(instance.id)


# ── Expense ──────────────────────────────────────────────────────────────────
@receiver(post_save, sender=Expense, dispatch_uid="ledger_post_expense")
def _on_expense_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_expense(instance)


@receiver(post_delete, sender=Expense, dispatch_uid="ledger_reverse_expense")
def _on_expense_deleted(sender, instance, **kwargs):
    posting_rules.reverse_expense(instance.id)


# ── Transaction ──────────────────────────────────────────────────────────────
@receiver(post_save, sender=Transaction, dispatch_uid="ledger_post_transaction")
def _on_transaction_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_transaction(instance)


@receiver(post_delete, sender=Transaction, dispatch_uid="ledger_reverse_transaction")
def _on_transaction_deleted(sender, instance, **kwargs):
    posting_rules.reverse_transaction(instance.id)


# ── Invoice (accounts receivable) ────────────────────────────────────────────
@receiver(post_save, sender=Invoice, dispatch_uid="ledger_post_invoice")
def _on_invoice_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_invoice(instance)


@receiver(post_delete, sender=Invoice, dispatch_uid="ledger_reverse_invoice")
def _on_invoice_deleted(sender, instance, **kwargs):
    posting_rules.reverse_invoice(instance.id)


# ── Inventory movements (raw / finished goods) ───────────────────────────────
@receiver(post_save, sender=StockMovement, dispatch_uid="ledger_post_stock_movement")
def _on_stock_movement_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_stock_movement(instance)


@receiver(post_delete, sender=StockMovement, dispatch_uid="ledger_reverse_stock_movement")
def _on_stock_movement_deleted(sender, instance, **kwargs):
    posting_rules.reverse_stock_movement(instance.id)


# ── Processed-material movements & batches ───────────────────────────────────
@receiver(post_save, sender=ProcessedMaterialStockMovement,
          dispatch_uid="ledger_post_pm_movement")
def _on_pm_movement_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_pm_stock_movement(instance)


@receiver(post_delete, sender=ProcessedMaterialStockMovement,
          dispatch_uid="ledger_reverse_pm_movement")
def _on_pm_movement_deleted(sender, instance, **kwargs):
    posting_rules.reverse_pm_stock_movement(instance.id)


@receiver(post_save, sender=ProcessedMaterialBatch, dispatch_uid="ledger_post_pm_batch")
def _on_pm_batch_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_processed_batch(instance)


@receiver(post_delete, sender=ProcessedMaterialBatch,
          dispatch_uid="ledger_reverse_pm_batch")
def _on_pm_batch_deleted(sender, instance, **kwargs):
    posting_rules.reverse_processed_batch(instance.id)


# ── Production runs ──────────────────────────────────────────────────────────
@receiver(post_save, sender=ProductionRun, dispatch_uid="ledger_post_production_run")
def _on_production_run_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    posting_rules.post_production_run(instance)


@receiver(post_delete, sender=ProductionRun, dispatch_uid="ledger_reverse_production_run")
def _on_production_run_deleted(sender, instance, **kwargs):
    posting_rules.reverse_production_run(instance.id)
