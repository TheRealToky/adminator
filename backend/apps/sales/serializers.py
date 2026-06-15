from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product
from apps.finance.models import Wallet

from . import services
from .models import PaymentMethod, Sale, SaleChannel, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = SaleItem
        fields = (
            "id", "product", "product_name", "product_sku",
            "quantity", "unit_price", "unit_cost", "line_total",
        )
        read_only_fields = ("id", "product_name", "product_sku", "unit_cost", "line_total")


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    served_by_name = serializers.CharField(source="served_by.full_name", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    wallet_name = serializers.CharField(source="wallet.name", read_only=True)

    class Meta:
        model = Sale
        fields = (
            "id", "receipt_number", "occurred_at",
            "channel", "channel_display",
            "payment_method", "payment_method_display",
            "customer_name", "customer_phone",
            "subtotal", "discount", "total", "cost_of_goods", "profit",
            "notes", "served_by", "served_by_name", "wallet", "wallet_name", "items",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "receipt_number", "subtotal", "total", "cost_of_goods", "profit",
            "items", "served_by_name", "wallet_name", "payment_method_display", "channel_display",
            "created_at", "updated_at",
        )


class SaleItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )


class SaleCreateSerializer(serializers.Serializer):
    items = SaleItemInputSerializer(many=True)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    channel = serializers.ChoiceField(
        choices=SaleChannel.choices, default=SaleChannel.COUNTER
    )
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"), min_value=Decimal("0")
    )
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    occurred_at = serializers.DateTimeField(required=False)
    wallet = serializers.PrimaryKeyRelatedField(
        queryset=Wallet.objects.all(), required=False, allow_null=True
    )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.create_sale(
            items=self.validated_data["items"],
            payment_method=self.validated_data["payment_method"],
            channel=self.validated_data["channel"],
            discount=self.validated_data["discount"],
            customer_name=self.validated_data.get("customer_name", ""),
            customer_phone=self.validated_data.get("customer_phone", ""),
            notes=self.validated_data.get("notes", ""),
            occurred_at=self.validated_data.get("occurred_at"),
            user=user,
            wallet=self.validated_data.get("wallet"),
        )


class SaleUpdateSerializer(SaleCreateSerializer):
    """Edit an existing sale, reusing the create payload shape."""

    def save(self, **kwargs):
        user = self.context["request"].user
        return services.update_sale(
            sale=self.instance,
            items=self.validated_data["items"],
            payment_method=self.validated_data["payment_method"],
            channel=self.validated_data["channel"],
            discount=self.validated_data["discount"],
            customer_name=self.validated_data.get("customer_name", ""),
            customer_phone=self.validated_data.get("customer_phone", ""),
            notes=self.validated_data.get("notes", ""),
            occurred_at=self.validated_data.get("occurred_at"),
            user=user,
            wallet=self.validated_data.get("wallet"),
        )


class PaymentMethodChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def list_all() -> list[dict[str, str]]:
        return [{"value": v, "label": label} for v, label in PaymentMethod.choices]


class SaleChannelChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def list_all() -> list[dict[str, str]]:
        return [{"value": v, "label": label} for v, label in SaleChannel.choices]
