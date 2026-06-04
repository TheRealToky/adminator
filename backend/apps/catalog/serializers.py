from __future__ import annotations

from rest_framework import serializers

from . import services
from .models import Product, ProductCategory, RawMaterial, RecipeItem, Supplier, UnitOfMeasure


class ProductCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductCategory
        fields = ("id", "name", "description", "product_count", "created_at", "updated_at")
        read_only_fields = ("id", "product_count", "created_at", "updated_at")


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id", "name", "contact_name", "phone", "email", "address",
            "notes", "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class RawMaterialUsedInProductSerializer(serializers.ModelSerializer):
    """Nested view: a product recipe line that uses this raw material."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = RecipeItem
        fields = ("id", "product", "product_name", "product_sku", "quantity")
        read_only_fields = fields


class RawMaterialSerializer(serializers.ModelSerializer):
    preferred_supplier_name = serializers.CharField(
        source="preferred_supplier.name", read_only=True
    )
    used_in_products = RawMaterialUsedInProductSerializer(
        source="used_in", many=True, read_only=True
    )
    used_in_processed_materials = serializers.SerializerMethodField()

    class Meta:
        model = RawMaterial
        fields = (
            "id", "sku", "name", "unit", "unit_cost",
            "reorder_threshold", "preferred_supplier", "preferred_supplier_name",
            "is_active",
            "used_in_products", "used_in_processed_materials",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "preferred_supplier_name",
            "used_in_products", "used_in_processed_materials",
            "created_at", "updated_at",
        )

    def get_used_in_processed_materials(self, obj: RawMaterial) -> list[dict]:
        # Imported lazily to avoid a cross-app import cycle at module load time
        # (processed_materials depends on catalog).
        items = obj.used_in_processed.select_related("processed_material").all()
        return [
            {
                "id": str(item.id),
                "processed_material": str(item.processed_material_id),
                "processed_material_name": item.processed_material.name,
                "processed_material_sku": item.processed_material.sku,
                "processed_material_unit": item.processed_material.unit,
                "quantity": str(item.quantity),
            }
            for item in items
        ]


class RecipeItemSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)
    raw_material_unit = serializers.CharField(source="raw_material.unit", read_only=True)
    raw_material_unit_cost = serializers.DecimalField(
        source="raw_material.unit_cost", max_digits=12, decimal_places=4, read_only=True
    )

    class Meta:
        model = RecipeItem
        fields = (
            "id", "product", "raw_material", "raw_material_name", "raw_material_unit",
            "raw_material_unit_cost", "quantity",
        )
        read_only_fields = ("id", "raw_material_name", "raw_material_unit", "raw_material_unit_cost")


class RecipeItemNestedSerializer(serializers.ModelSerializer):
    """Used when nesting recipe items inside a Product payload."""

    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)
    raw_material_unit = serializers.CharField(source="raw_material.unit", read_only=True)

    class Meta:
        model = RecipeItem
        fields = ("id", "raw_material", "raw_material_name", "raw_material_unit", "quantity")
        read_only_fields = ("id", "raw_material_name", "raw_material_unit")


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    margin = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    recipe_items = RecipeItemNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "sku", "name", "category", "category_name", "description",
            "unit", "selling_price", "production_cost", "margin",
            "overhead_pct", "reorder_threshold", "is_active", "recipe_items",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "category_name", "margin", "recipe_items",
                            "production_cost", "created_at", "updated_at")

    def update(self, instance, validated_data):
        overhead_changed = (
            "overhead_pct" in validated_data
            and validated_data["overhead_pct"] != instance.overhead_pct
        )
        instance = super().update(instance, validated_data)
        if overhead_changed:
            services.refresh_product_unit_cost(instance)
            instance.refresh_from_db(fields=["production_cost"])
        return instance


class UnitChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def list_all() -> list[dict[str, str]]:
        return [{"value": v, "label": label} for v, label in UnitOfMeasure.choices]
