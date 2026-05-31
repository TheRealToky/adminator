"""Signal hooks that wire processed-material consumption into product production.

We deliberately keep this in a separate module so the catalog / production / inventory
apps don't import anything from processed_materials. The dependency goes one way:
processed_materials → catalog / production / inventory.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog import services as catalog_services
from apps.production.models import ProductionRun, ProductionStatus

from . import services
from .models import ProcessedMaterialRecipeItem, ProductProcessedMaterialUsage


@receiver(post_save, sender=ProductionRun, dispatch_uid="processed_materials.on_production_run")
def on_production_run_saved(sender, instance: ProductionRun, created: bool, **kwargs) -> None:
    """When a completed ProductionRun is created, draw down processed materials used by the product."""
    # Only act on creation of a completed run — updates (cost recomputation,
    # status changes) shouldn't double-decrement stock.
    if not created or instance.status != ProductionStatus.COMPLETED:
        return

    # Cheap early-out: nothing to do if the product doesn't use any processed materials.
    if not instance.product.processed_usages.exists():
        return

    services.consume_for_product_run(
        product=instance.product,
        product_quantity=Decimal(instance.quantity),
        reference=f"PROD-{instance.id}",
        user=instance.created_by,
        allow_negative=True,  # demo seeds may run before stock is built up
    )


@receiver(post_save, sender=ProductProcessedMaterialUsage, dispatch_uid="processed_materials.usage.refresh_product_cost")
def on_processed_usage_saved(sender, instance: ProductProcessedMaterialUsage, **kwargs) -> None:
    catalog_services.refresh_product_unit_cost(instance.product)


@receiver(post_delete, sender=ProductProcessedMaterialUsage, dispatch_uid="processed_materials.usage.refresh_product_cost_on_delete")
def on_processed_usage_deleted(sender, instance: ProductProcessedMaterialUsage, **kwargs) -> None:
    catalog_services.refresh_product_unit_cost(instance.product)


@receiver(post_save, sender=ProcessedMaterialRecipeItem, dispatch_uid="processed_materials.recipe_item.refresh_unit_cost")
def on_recipe_item_saved(sender, instance: ProcessedMaterialRecipeItem, **kwargs) -> None:
    services.refresh_unit_cost(instance.processed_material)


@receiver(post_delete, sender=ProcessedMaterialRecipeItem, dispatch_uid="processed_materials.recipe_item.refresh_unit_cost_on_delete")
def on_recipe_item_deleted(sender, instance: ProcessedMaterialRecipeItem, **kwargs) -> None:
    services.refresh_unit_cost(instance.processed_material)
