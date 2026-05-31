from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product

from . import services
from .models import ProductionRun, ProductionStatus


class ProductionRunSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = ProductionRun
        fields = (
            "id", "product", "product_name", "product_sku",
            "quantity", "status", "scheduled_for", "completed_at",
            "cost", "notes", "created_by", "created_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "product_name", "product_sku", "cost", "completed_at",
            "created_by", "created_by_name", "created_at", "updated_at",
        )


class ProductionExecuteSerializer(serializers.Serializer):
    """Run production now: consume raw materials, add finished stock."""

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    scheduled_for = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=ProductionStatus.choices, default=ProductionStatus.COMPLETED
    )

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.execute_production(
            product=self.validated_data["product"],
            quantity=self.validated_data["quantity"],
            scheduled_for=self.validated_data.get("scheduled_for"),
            notes=self.validated_data.get("notes", ""),
            user=user,
            status=self.validated_data["status"],
        )
