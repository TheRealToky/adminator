from django.contrib import admin

from .models import ProductionRun


@admin.register(ProductionRun)
class ProductionRunAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "status", "scheduled_for",
                    "completed_at", "cost", "created_by")
    list_filter = ("status", "scheduled_for")
    search_fields = ("product__name", "product__sku", "notes")
    autocomplete_fields = ("product", "created_by")
    readonly_fields = ("cost", "completed_at", "created_at", "updated_at")
