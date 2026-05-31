from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("unit_cost", "line_total")
    autocomplete_fields = ("product",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "occurred_at", "payment_method",
                    "channel", "total", "profit", "served_by")
    list_filter = ("payment_method", "channel", "occurred_at")
    search_fields = ("receipt_number", "customer_name", "customer_phone")
    autocomplete_fields = ("served_by",)
    inlines = [SaleItemInline]
    readonly_fields = ("receipt_number", "subtotal", "total",
                       "cost_of_goods", "created_at", "updated_at")
