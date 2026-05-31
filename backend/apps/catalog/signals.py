"""Keep Product.production_cost in sync with recipe edits.

A RecipeItem mutation (create/update/delete) recomputes the parent product's
per-unit cost. ProductProcessedMaterialUsage triggers the same refresh from
its own app (see apps/processed_materials/signals.py) to keep the dependency
direction one-way: processed_materials → catalog.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import RecipeItem


@receiver(post_save, sender=RecipeItem, dispatch_uid="catalog.recipe_item.refresh_cost")
def recipe_item_saved(sender, instance: RecipeItem, **kwargs) -> None:
    services.refresh_product_unit_cost(instance.product)


@receiver(post_delete, sender=RecipeItem, dispatch_uid="catalog.recipe_item.refresh_cost_on_delete")
def recipe_item_deleted(sender, instance: RecipeItem, **kwargs) -> None:
    services.refresh_product_unit_cost(instance.product)
