from django.contrib import admin

from .models import (
    ProcessedMaterial,
    ProcessedMaterialBatch,
    ProcessedMaterialRecipeItem,
    ProcessedMaterialStock,
    ProcessedMaterialStockMovement,
    ProductProcessedMaterialUsage,
)


class ProcessedMaterialRecipeItemInline(admin.TabularInline):
    model = ProcessedMaterialRecipeItem
    fk_name = "processed_material"
    extra = 1
    autocomplete_fields = ("raw_material", "sub_processed_material")


@admin.register(ProcessedMaterial)
class ProcessedMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "unit", "yield_per_batch", "unit_cost",
        "shelf_life_hours", "is_active",
    )
    list_filter = ("unit", "is_active")
    search_fields = ("name", "sku")
    inlines = [ProcessedMaterialRecipeItemInline]


@admin.register(ProcessedMaterialRecipeItem)
class ProcessedMaterialRecipeItemAdmin(admin.ModelAdmin):
    list_display = (
        "processed_material", "raw_material", "sub_processed_material", "quantity",
    )
    search_fields = (
        "processed_material__name",
        "raw_material__name",
        "sub_processed_material__name",
    )
    autocomplete_fields = (
        "processed_material", "raw_material", "sub_processed_material",
    )


@admin.register(ProductProcessedMaterialUsage)
class ProductProcessedMaterialUsageAdmin(admin.ModelAdmin):
    list_display = ("product", "processed_material", "quantity")
    search_fields = ("product__name", "processed_material__name")
    autocomplete_fields = ("product", "processed_material")


@admin.register(ProcessedMaterialStock)
class ProcessedMaterialStockAdmin(admin.ModelAdmin):
    list_display = ("processed_material", "quantity", "is_low", "updated_at")
    search_fields = ("processed_material__name", "processed_material__sku")
    autocomplete_fields = ("processed_material",)


@admin.register(ProcessedMaterialStockMovement)
class ProcessedMaterialStockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "stock", "reason", "quantity_delta", "balance_after",
        "reference", "created_at",
    )
    list_filter = ("reason",)
    search_fields = ("reference", "note")
    readonly_fields = ("created_at", "updated_at", "balance_after")


@admin.register(ProcessedMaterialBatch)
class ProcessedMaterialBatchAdmin(admin.ModelAdmin):
    list_display = (
        "processed_material", "batches", "quantity_produced",
        "scheduled_for", "completed_at", "cost",
    )
    list_filter = ("scheduled_for",)
    search_fields = ("processed_material__name", "notes")
    autocomplete_fields = ("processed_material", "created_by")
    readonly_fields = ("cost", "completed_at", "quantity_produced",
                       "created_at", "updated_at")
