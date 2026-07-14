from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import ZERO, Account, AccountingPeriod, JournalEntry, JournalLine


class AccountSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    normal_balance = serializers.CharField(read_only=True)
    parent_code = serializers.CharField(source="parent.code", read_only=True)

    class Meta:
        model = Account
        fields = (
            "id", "code", "name", "type", "type_display", "subtype",
            "parent", "parent_code", "is_postable", "is_active",
            "normal_balance", "currency", "description",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = (
            "id", "account", "account_code", "account_name",
            "debit", "credit", "memo", "wallet",
        )
        read_only_fields = ("id",)


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)
    period_label = serializers.CharField(source="period.label", read_only=True)
    total_debit = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    is_balanced = serializers.BooleanField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = (
            "id", "date", "period", "period_label", "memo",
            "source_type", "source_id", "event", "status", "is_system",
            "reversal_of", "lines", "total_debit", "total_credit", "is_balanced",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class AccountingPeriodSerializer(serializers.ModelSerializer):
    is_postable = serializers.BooleanField(read_only=True)

    class Meta:
        model = AccountingPeriod
        fields = ("id", "start_date", "label", "status", "is_postable", "closed_at")
        read_only_fields = ("id", "start_date", "label", "closed_at")


class ManualJournalLineInputSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    debit = serializers.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    credit = serializers.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    memo = serializers.CharField(max_length=240, required=False, allow_blank=True)

    def validate(self, attrs):
        debit = attrs.get("debit") or ZERO
        credit = attrs.get("credit") or ZERO
        if debit < ZERO or credit < ZERO:
            raise serializers.ValidationError("Amounts cannot be negative.")
        if bool(debit) == bool(credit):
            raise serializers.ValidationError(
                "Each line needs exactly one of debit or credit."
            )
        if not attrs["account"].is_postable:
            raise serializers.ValidationError(
                f"Account {attrs['account'].code} is not postable."
            )
        return attrs


class ManualJournalEntrySerializer(serializers.Serializer):
    """Validate a hand-entered, balanced journal entry before posting it."""

    date = serializers.DateField()
    memo = serializers.CharField(max_length=240, required=False, allow_blank=True)
    lines = ManualJournalLineInputSerializer(many=True)

    def validate_lines(self, lines):
        if len(lines) < 2:
            raise serializers.ValidationError("A journal entry needs at least two lines.")
        total_debit = sum((Decimal(l.get("debit") or ZERO) for l in lines), ZERO)
        total_credit = sum((Decimal(l.get("credit") or ZERO) for l in lines), ZERO)
        if total_debit != total_credit:
            raise serializers.ValidationError(
                f"Entry does not balance: debit {total_debit} != credit {total_credit}."
            )
        return lines
