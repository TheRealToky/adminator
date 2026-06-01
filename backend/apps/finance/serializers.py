from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    Budget,
    Expense,
    ExpenseCategory,
    Invoice,
    InvoiceStatus,
    Transaction,
    TransactionCategory,
)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "name", "description", "is_active",
                  "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = Expense
        fields = (
            "id", "category", "category_name", "title", "amount",
            "incurred_on", "payment_method", "payment_method_display",
            "supplier", "supplier_name", "reference", "notes",
            "recorded_by", "recorded_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "category_name", "supplier_name", "recorded_by", "recorded_by_name",
            "payment_method_display", "created_at", "updated_at",
        )

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user
        return super().create(validated_data)


class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    issued_by_name = serializers.CharField(source="issued_by.full_name", read_only=True)
    balance_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id", "invoice_number", "customer_name", "customer_email", "customer_phone",
            "issue_date", "due_date", "amount", "amount_paid", "balance_due",
            "status", "status_display", "is_overdue",
            "description", "notes", "paid_at",
            "issued_by", "issued_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "status_display", "balance_due", "is_overdue",
            "issued_by", "issued_by_name", "created_at", "updated_at",
        )

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["issued_by"] = request.user
        return super().create(validated_data)


class InvoicePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    def save(self, **kwargs):
        invoice: Invoice = self.context["invoice"]
        payment = self.validated_data["amount"]
        invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + payment
        update_fields = ["amount_paid", "updated_at"]

        if invoice.amount_paid >= invoice.amount:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = timezone.now()
            update_fields += ["status", "paid_at"]
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
            update_fields.append("status")

        invoice.save(update_fields=update_fields)
        return invoice


class TransactionCategorySerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)

    class Meta:
        model = TransactionCategory
        fields = ("id", "name", "direction", "direction_display",
                  "description", "is_active",
                  "created_at", "updated_at")
        read_only_fields = ("id", "direction_display", "created_at", "updated_at")


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_direction = serializers.CharField(source="category.direction", read_only=True)
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id", "direction", "direction_display",
            "category", "category_name", "category_direction",
            "title", "amount",
            "occurred_on", "payment_method", "payment_method_display",
            "counterparty", "reference", "notes",
            "recorded_by", "recorded_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "direction_display", "category_name", "category_direction",
            "payment_method_display",
            "recorded_by", "recorded_by_name",
            "created_at", "updated_at",
        )

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", None)
        direction = attrs.get("direction") or getattr(self.instance, "direction", None)
        if category and direction and category.direction != direction:
            raise serializers.ValidationError(
                {"category": "Category direction must match transaction direction."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user
        return super().create(validated_data)


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Budget
        fields = ("id", "category", "category_name", "month", "amount", "notes",
                  "created_at", "updated_at")
        read_only_fields = ("id", "category_name", "created_at", "updated_at")
