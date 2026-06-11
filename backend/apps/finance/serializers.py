from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Asset,
    Budget,
    Expense,
    ExpenseCategory,
    Invoice,
    InvoiceStatus,
    Transaction,
    TransactionCategory,
    Wallet,
    WalletEntry,
    WalletEntryType,
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
    wallet_name = serializers.CharField(source="wallet.name", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = Expense
        fields = (
            "id", "category", "category_name", "title", "amount",
            "incurred_on", "payment_method", "payment_method_display",
            "supplier", "supplier_name", "reference", "notes",
            "recorded_by", "recorded_by_name", "wallet", "wallet_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "category_name", "supplier_name", "recorded_by", "recorded_by_name",
            "wallet_name", "payment_method_display", "created_at", "updated_at",
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
    wallet_name = serializers.CharField(source="wallet.name", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id", "direction", "direction_display",
            "category", "category_name", "category_direction",
            "title", "amount",
            "occurred_on", "payment_method", "payment_method_display",
            "counterparty", "reference", "notes",
            "recorded_by", "recorded_by_name", "wallet", "wallet_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "direction_display", "category_name", "category_direction",
            "payment_method_display",
            "recorded_by", "recorded_by_name", "wallet_name",
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


class AssetSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)

    # Computed
    months_elapsed = serializers.IntegerField(read_only=True)
    accumulated_depreciation = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    carrying_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    is_fully_depreciated = serializers.BooleanField(read_only=True)

    # Optional auto-Expense linkage on create (write-only inputs)
    record_as_expense = serializers.BooleanField(
        write_only=True, required=False, default=False,
        help_text="If true, also create a finance.Expense for the purchase.",
    )
    expense_category = serializers.PrimaryKeyRelatedField(
        write_only=True, required=False, allow_null=True,
        queryset=ExpenseCategory.objects.all(),
        help_text="ExpenseCategory for the auto-created Expense. Required when record_as_expense is true.",
    )
    linked_expense_title = serializers.CharField(
        source="linked_expense.title", read_only=True,
    )

    class Meta:
        model = Asset
        fields = (
            "id", "name", "category", "category_display",
            "purchase_date", "purchase_cost",
            "useful_life_months", "status", "status_display",
            "supplier", "supplier_name", "reference", "notes",
            "linked_expense", "linked_expense_title",
            "recorded_by", "recorded_by_name",
            "months_elapsed", "accumulated_depreciation",
            "carrying_value", "is_fully_depreciated",
            "record_as_expense", "expense_category",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "category_display", "status_display",
            "supplier_name", "recorded_by", "recorded_by_name",
            "linked_expense", "linked_expense_title",
            "months_elapsed", "accumulated_depreciation",
            "carrying_value", "is_fully_depreciated",
            "created_at", "updated_at",
        )

    def validate(self, attrs):
        if attrs.get("record_as_expense") and not attrs.get("expense_category"):
            raise serializers.ValidationError(
                {"expense_category": "Required when recording as an expense."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        record_as_expense = validated_data.pop("record_as_expense", False)
        expense_category = validated_data.pop("expense_category", None)

        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user

        if record_as_expense and expense_category:
            user = request.user if request and request.user.is_authenticated else None
            expense = Expense.objects.create(
                category=expense_category,
                title=validated_data["name"],
                amount=validated_data["purchase_cost"],
                incurred_on=validated_data.get("purchase_date") or timezone.localdate(),
                supplier=validated_data.get("supplier"),
                reference=validated_data.get("reference", ""),
                notes=f"Asset purchase: {validated_data['name']}",
                recorded_by=user,
            )
            validated_data["linked_expense"] = expense

        return super().create(validated_data)


# ── Wallets ────────────────────────────────────────────────────────────────
class WalletSerializer(serializers.ModelSerializer):
    account_type_display = serializers.CharField(
        source="get_account_type_display", read_only=True
    )
    current_balance = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    recorded_by_name = serializers.CharField(
        source="recorded_by.full_name", read_only=True
    )

    class Meta:
        model = Wallet
        fields = (
            "id", "name", "account_type", "account_type_display",
            "opening_balance", "current_balance",
            "institution", "account_number", "is_active", "notes",
            "recorded_by", "recorded_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "account_type_display", "current_balance",
            "recorded_by", "recorded_by_name", "created_at", "updated_at",
        )

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user
        return super().create(validated_data)


class WalletEntrySerializer(serializers.ModelSerializer):
    entry_type_display = serializers.CharField(
        source="get_entry_type_display", read_only=True
    )
    signed_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    wallet_name = serializers.CharField(source="wallet.name", read_only=True)
    counterparty_wallet_name = serializers.CharField(
        source="counterparty_wallet.name", read_only=True
    )
    recorded_by_name = serializers.CharField(
        source="recorded_by.full_name", read_only=True
    )

    class Meta:
        model = WalletEntry
        fields = (
            "id", "wallet", "wallet_name",
            "entry_type", "entry_type_display",
            "amount", "signed_amount", "occurred_on",
            "description", "reference",
            "counterparty_wallet", "counterparty_wallet_name",
            "transfer_group",
            "recorded_by", "recorded_by_name",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class WalletMovementSerializer(serializers.Serializer):
    """Shared input for a deposit or a withdrawal against a single wallet.

    The concrete ``entry_type`` is supplied by the view via ``context``.
    """

    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    occurred_on = serializers.DateField(required=False)
    description = serializers.CharField(
        max_length=160, required=False, allow_blank=True
    )
    reference = serializers.CharField(
        max_length=80, required=False, allow_blank=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def save(self, **kwargs):
        wallet: Wallet = self.context["wallet"]
        entry_type: str = self.context["entry_type"]
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        data = self.validated_data
        return WalletEntry.objects.create(
            wallet=wallet,
            entry_type=entry_type,
            amount=data["amount"],
            occurred_on=data.get("occurred_on") or timezone.localdate(),
            description=data.get("description", ""),
            reference=data.get("reference", ""),
            notes=data.get("notes", ""),
            recorded_by=user,
        )


class WalletTransferSerializer(serializers.Serializer):
    """Move money from the wallet in context to another wallet."""

    destination = serializers.PrimaryKeyRelatedField(queryset=Wallet.objects.all())
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    occurred_on = serializers.DateField(required=False)
    description = serializers.CharField(
        max_length=160, required=False, allow_blank=True
    )
    reference = serializers.CharField(
        max_length=80, required=False, allow_blank=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_destination(self, dest: Wallet) -> Wallet:
        source: Wallet = self.context["wallet"]
        if dest.id == source.id:
            raise serializers.ValidationError("Cannot transfer to the same wallet.")
        if not dest.is_active:
            raise serializers.ValidationError("Destination wallet is inactive.")
        return dest

    @db_transaction.atomic
    def save(self, **kwargs):
        source: Wallet = self.context["wallet"]
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        data = self.validated_data
        dest: Wallet = data["destination"]
        group = uuid.uuid4()
        occurred_on = data.get("occurred_on") or timezone.localdate()
        description = data.get("description", "")
        reference = data.get("reference", "")
        notes = data.get("notes", "")

        out_entry = WalletEntry.objects.create(
            wallet=source,
            entry_type=WalletEntryType.TRANSFER_OUT,
            amount=data["amount"],
            occurred_on=occurred_on,
            description=description or f"Transfer to {dest.name}",
            reference=reference,
            counterparty_wallet=dest,
            transfer_group=group,
            notes=notes,
            recorded_by=user,
        )
        WalletEntry.objects.create(
            wallet=dest,
            entry_type=WalletEntryType.TRANSFER_IN,
            amount=data["amount"],
            occurred_on=occurred_on,
            description=description or f"Transfer from {source.name}",
            reference=reference,
            counterparty_wallet=source,
            transfer_group=group,
            notes=notes,
            recorded_by=user,
        )
        return out_entry
