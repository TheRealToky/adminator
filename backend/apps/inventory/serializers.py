from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product, RawMaterial

from . import services
from .models import MovementReason, StockItem, StockMovement


class StockItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(read_only=True)
    item_sku = serializers.CharField(read_only=True)
    item_unit = serializers.CharField(read_only=True)
    reorder_threshold = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockItem
        fields = (
            "id", "kind", "product", "raw_material",
            "item_name", "item_sku", "item_unit",
            "quantity", "reorder_threshold", "is_low",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "kind", "item_name", "item_sku", "item_unit",
            "reorder_threshold", "is_low", "created_at", "updated_at",
        )


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="stock_item.item_name", read_only=True)
    item_sku = serializers.CharField(source="stock_item.item_sku", read_only=True)
    item_unit = serializers.CharField(source="stock_item.item_unit", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id", "stock_item", "item_name", "item_sku", "item_unit",
            "reason", "reason_display", "quantity_delta", "balance_after",
            "reference", "note", "created_by", "created_by_name", "created_at",
        )
        read_only_fields = fields


class StockAdjustSerializer(serializers.Serializer):
    """Manual stock adjustment by ops staff."""

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    raw_material = serializers.PrimaryKeyRelatedField(
        queryset=RawMaterial.objects.all(), required=False, allow_null=True
    )
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=4)
    note = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        product = attrs.get("product")
        raw_material = attrs.get("raw_material")
        if (product is None) == (raw_material is None):
            raise serializers.ValidationError(
                "Provide exactly one of `product` or `raw_material`."
            )
        if attrs["quantity_delta"] == 0:
            raise serializers.ValidationError({"quantity_delta": "Must be non-zero."})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        product = self.validated_data.get("product")
        raw_material = self.validated_data.get("raw_material")
        delta: Decimal = self.validated_data["quantity_delta"]
        reason = (
            MovementReason.ADJUSTMENT_IN if delta > 0 else MovementReason.ADJUSTMENT_OUT
        )
        stock = services.ensure_stock_item(product=product, raw_material=raw_material)
        return services.adjust_stock(
            stock_item=stock,
            quantity_delta=delta,
            reason=reason,
            reference=self.validated_data.get("reference", ""),
            note=self.validated_data.get("note", ""),
            user=user,
        )


class RawMaterialReceiveSerializer(serializers.Serializer):
    raw_material = serializers.PrimaryKeyRelatedField(queryset=RawMaterial.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    reference = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.receive_raw_material(
            raw_material=self.validated_data["raw_material"],
            quantity=self.validated_data["quantity"],
            reference=self.validated_data.get("reference", ""),
            note=self.validated_data.get("note", ""),
            user=user,
        )


class StockWriteOffSerializer(serializers.Serializer):
    """Write off finished product or raw material as waste/loss."""

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    raw_material = serializers.PrimaryKeyRelatedField(
        queryset=RawMaterial.objects.all(), required=False, allow_null=True
    )
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0.0001")
    )
    note = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        if (attrs.get("product") is None) == (attrs.get("raw_material") is None):
            raise serializers.ValidationError(
                "Provide exactly one of `product` or `raw_material`."
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.record_waste(
            product=self.validated_data.get("product"),
            raw_material=self.validated_data.get("raw_material"),
            quantity=self.validated_data["quantity"],
            note=self.validated_data.get("note", ""),
            reference=self.validated_data.get("reference", ""),
            user=user,
        )
