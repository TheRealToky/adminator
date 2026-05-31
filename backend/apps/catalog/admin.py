from django.contrib import admin

from .models import Product, ProductCategory, RawMaterial, RecipeItem, Supplier


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_name", "phone", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_name", "phone", "email")


@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "unit", "unit_cost", "preferred_supplier", "is_active")
    list_filter = ("unit", "is_active", "preferred_supplier")
    search_fields = ("name", "sku")


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1
    autocomplete_fields = ("raw_material",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "selling_price", "production_cost", "is_active")
    list_filter = ("category", "is_active", "unit")
    search_fields = ("name", "sku")
    inlines = [RecipeItemInline]
    autocomplete_fields = ("category",)


@admin.register(RecipeItem)
class RecipeItemAdmin(admin.ModelAdmin):
    list_display = ("product", "raw_material", "quantity")
    search_fields = ("product__name", "raw_material__name")
    autocomplete_fields = ("product", "raw_material")
