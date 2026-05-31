from django.contrib import admin

from .models import StockItem, StockMovement


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("item_name", "item_sku", "kind", "quantity", "is_low", "updated_at")
    list_filter = ("kind",)
    search_fields = ("product__name", "product__sku",
                     "raw_material__name", "raw_material__sku")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("stock_item", "reason", "quantity_delta",
                    "balance_after", "reference", "created_at")
    list_filter = ("reason",)
    search_fields = ("reference", "note", "stock_item__product__name",
                     "stock_item__raw_material__name")
    raw_id_fields = ("stock_item",)
    readonly_fields = ("created_at", "updated_at", "balance_after")
