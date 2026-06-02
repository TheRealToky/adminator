from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product, RawMaterial

from . import services
from .models import (
    ProcessedMaterial,
    ProcessedMaterialBatch,
    ProcessedMaterialMovementReason,
    ProcessedMaterialRecipeItem,
    ProcessedMaterialStock,
    ProcessedMaterialStockMovement,
    ProductProcessedMaterialUsage,
)


def _ancestors_of(processed_material_id) -> set:
    """All processed materials that (transitively) include the given one.

    Used to block recipe cycles: a sub-ingredient cannot be one of its own
    ancestors (or itself). Walks the ``used_in_processed_materials`` reverse
    relation breadth-first.
    """
    ancestors: set = set()
    frontier = {processed_material_id}
    while frontier:
        parents = set(
            ProcessedMaterialRecipeItem.objects
            .filter(sub_processed_material_id__in=frontier)
            .values_list("processed_material_id", flat=True)
        )
        new = parents - ancestors
        if not new:
            break
        ancestors |= new
        frontier = new
    return ancestors


# ── Recipe & usage (nested previews) ──────────────────────────────────────
class ProcessedMaterialRecipeItemNestedSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(
        source="raw_material.name", read_only=True
    )
    raw_material_unit = serializers.CharField(
        source="raw_material.unit", read_only=True
    )
    sub_processed_material_name = serializers.CharField(
        source="sub_processed_material.name", read_only=True
    )
    sub_processed_material_unit = serializers.CharField(
        source="sub_processed_material.unit", read_only=True
    )

    class Meta:
        model = ProcessedMaterialRecipeItem
        fields = (
            "id", "raw_material", "raw_material_name", "raw_material_unit",
            "sub_processed_material",
            "sub_processed_material_name", "sub_processed_material_unit",
            "quantity",
        )
        read_only_fields = (
            "id", "raw_material_name", "raw_material_unit",
            "sub_processed_material_name", "sub_processed_material_unit",
        )


class ProductProcessedMaterialUsageNestedSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = ProductProcessedMaterialUsage
        fields = ("id", "product", "product_name", "product_sku", "quantity")
        read_only_fields = ("id", "product_name", "product_sku")


# ── ProcessedMaterial ─────────────────────────────────────────────────────
class ProcessedMaterialSerializer(serializers.ModelSerializer):
    recipe_items = ProcessedMaterialRecipeItemNestedSerializer(many=True, read_only=True)
    used_in_products = ProductProcessedMaterialUsageNestedSerializer(many=True, read_only=True)
    stock_quantity = serializers.SerializerMethodField()
    is_low = serializers.SerializerMethodField()

    class Meta:
        model = ProcessedMaterial
        fields = (
            "id", "sku", "name", "unit", "yield_per_batch", "unit_cost",
            "overhead_pct", "shelf_life_hours", "reorder_threshold",
            "notes", "is_active",
            "recipe_items", "used_in_products",
            "stock_quantity", "is_low",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "unit_cost", "recipe_items", "used_in_products",
            "stock_quantity", "is_low", "created_at", "updated_at",
        )

    def get_stock_quantity(self, obj: ProcessedMaterial) -> str:
        stock = getattr(obj, "stock", None)
        return str(stock.quantity) if stock else "0"

    def get_is_low(self, obj: ProcessedMaterial) -> bool:
        stock = getattr(obj, "stock", None)
        if not stock:
            return Decimal(obj.reorder_threshold) > 0
        return Decimal(stock.quantity) <= Decimal(obj.reorder_threshold)

    def update(self, instance, validated_data):
        overhead_changed = (
            "overhead_pct" in validated_data
            and validated_data["overhead_pct"] != instance.overhead_pct
        )
        instance = super().update(instance, validated_data)
        if overhead_changed:
            services.refresh_unit_cost(instance)
            instance.refresh_from_db(fields=["unit_cost"])
        return instance


# ── Recipe item (CRUD) ────────────────────────────────────────────────────
class ProcessedMaterialRecipeItemSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True)
    raw_material_unit = serializers.CharField(source="raw_material.unit", read_only=True)
    raw_material_unit_cost = serializers.DecimalField(
        source="raw_material.unit_cost", max_digits=12, decimal_places=4, read_only=True
    )
    sub_processed_material_name = serializers.CharField(
        source="sub_processed_material.name", read_only=True
    )
    sub_processed_material_unit = serializers.CharField(
        source="sub_processed_material.unit", read_only=True
    )
    sub_processed_material_unit_cost = serializers.DecimalField(
        source="sub_processed_material.unit_cost",
        max_digits=12, decimal_places=4, read_only=True,
    )

    class Meta:
        model = ProcessedMaterialRecipeItem
        fields = (
            "id", "processed_material",
            "raw_material",
            "raw_material_name", "raw_material_unit", "raw_material_unit_cost",
            "sub_processed_material",
            "sub_processed_material_name", "sub_processed_material_unit",
            "sub_processed_material_unit_cost",
            "quantity",
        )
        read_only_fields = (
            "id",
            "raw_material_name", "raw_material_unit", "raw_material_unit_cost",
            "sub_processed_material_name", "sub_processed_material_unit",
            "sub_processed_material_unit_cost",
        )
        extra_kwargs = {
            "raw_material": {"required": False, "allow_null": True},
            "sub_processed_material": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        raw = attrs.get(
            "raw_material",
            instance.raw_material if instance else None,
        )
        sub = attrs.get(
            "sub_processed_material",
            instance.sub_processed_material if instance else None,
        )
        if bool(raw) == bool(sub):
            raise serializers.ValidationError(
                "Provide exactly one of `raw_material` or `sub_processed_material`."
            )
        if sub is not None:
            parent = attrs.get(
                "processed_material",
                instance.processed_material if instance else None,
            )
            if parent is not None and sub.pk == parent.pk:
                raise serializers.ValidationError({
                    "sub_processed_material":
                        "A processed material cannot include itself.",
                })
            if parent is not None and sub.pk in _ancestors_of(parent.pk):
                raise serializers.ValidationError({
                    "sub_processed_material":
                        f"Adding '{sub.name}' would create a cycle — "
                        f"it already (directly or indirectly) includes '{parent.name}'.",
                })
        return attrs


# ── ProductProcessedMaterialUsage (CRUD) ──────────────────────────────────
class ProductProcessedMaterialUsageSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    processed_material_name = serializers.CharField(
        source="processed_material.name", read_only=True
    )
    processed_material_unit = serializers.CharField(
        source="processed_material.unit", read_only=True
    )
    processed_material_unit_cost = serializers.DecimalField(
        source="processed_material.unit_cost",
        max_digits=12, decimal_places=4, read_only=True,
    )

    class Meta:
        model = ProductProcessedMaterialUsage
        fields = (
            "id", "product", "product_name", "product_sku",
            "processed_material", "processed_material_name", "processed_material_unit",
            "processed_material_unit_cost", "quantity",
        )
        read_only_fields = (
            "id", "product_name", "product_sku",
            "processed_material_name", "processed_material_unit",
            "processed_material_unit_cost",
        )


# ── Stock ─────────────────────────────────────────────────────────────────
class ProcessedMaterialStockSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(read_only=True)
    item_sku = serializers.CharField(read_only=True)
    item_unit = serializers.CharField(read_only=True)
    item_unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )
    reorder_threshold = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProcessedMaterialStock
        fields = (
            "id", "processed_material", "item_name", "item_sku", "item_unit",
            "item_unit_cost",
            "quantity", "reorder_threshold", "is_low",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class ProcessedMaterialStockAdjustSerializer(serializers.Serializer):
    processed_material = serializers.PrimaryKeyRelatedField(
        queryset=ProcessedMaterial.objects.all()
    )
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=4)
    note = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["quantity_delta"] == 0:
            raise serializers.ValidationError(
                {"quantity_delta": "Must be non-zero."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        delta: Decimal = self.validated_data["quantity_delta"]
        reason = (
            ProcessedMaterialMovementReason.ADJUSTMENT_IN if delta > 0
            else ProcessedMaterialMovementReason.ADJUSTMENT_OUT
        )
        stock = services.ensure_stock(self.validated_data["processed_material"])
        return services.adjust_stock(
            stock=stock,
            quantity_delta=delta,
            reason=reason,
            reference=self.validated_data.get("reference", ""),
            note=self.validated_data.get("note", ""),
            user=user,
        )


class ProcessedMaterialStockWriteOffSerializer(serializers.Serializer):
    """Write off processed-material stock as waste/loss.

    Decrements stock and books an Expense at ``unit_cost × quantity`` under the
    shared "Inventory write-off" category.
    """

    processed_material = serializers.PrimaryKeyRelatedField(
        queryset=ProcessedMaterial.objects.all()
    )
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0.0001")
    )
    note = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.record_waste(
            processed_material=self.validated_data["processed_material"],
            quantity=self.validated_data["quantity"],
            note=self.validated_data.get("note", ""),
            reference=self.validated_data.get("reference", ""),
            user=user,
        )


# ── Stock movement ────────────────────────────────────────────────────────
class ProcessedMaterialStockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="stock.item_name", read_only=True)
    item_sku = serializers.CharField(source="stock.item_sku", read_only=True)
    item_unit = serializers.CharField(source="stock.item_unit", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model = ProcessedMaterialStockMovement
        fields = (
            "id", "stock", "item_name", "item_sku", "item_unit",
            "reason", "reason_display", "quantity_delta", "balance_after",
            "reference", "note", "created_by", "created_by_name", "created_at",
        )
        read_only_fields = fields


# ── Batch ─────────────────────────────────────────────────────────────────
class ProcessedMaterialBatchSerializer(serializers.ModelSerializer):
    processed_material_name = serializers.CharField(
        source="processed_material.name", read_only=True
    )
    processed_material_sku = serializers.CharField(
        source="processed_material.sku", read_only=True
    )
    processed_material_unit = serializers.CharField(
        source="processed_material.unit", read_only=True
    )
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = ProcessedMaterialBatch
        fields = (
            "id", "processed_material", "processed_material_name",
            "processed_material_sku", "processed_material_unit",
            "batches", "quantity_produced", "cost",
            "scheduled_for", "completed_at", "notes",
            "created_by", "created_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "processed_material_name", "processed_material_sku",
            "processed_material_unit", "quantity_produced", "cost",
            "completed_at", "created_by", "created_by_name",
            "created_at", "updated_at",
        )


class ProcessedMaterialBatchProduceSerializer(serializers.Serializer):
    processed_material = serializers.PrimaryKeyRelatedField(
        queryset=ProcessedMaterial.objects.all()
    )
    batches = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
        default=Decimal("1"),
    )
    scheduled_for = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.produce_batch(
            processed_material=self.validated_data["processed_material"],
            batches=self.validated_data["batches"],
            scheduled_for=self.validated_data.get("scheduled_for"),
            notes=self.validated_data.get("notes", ""),
            user=user,
        )
