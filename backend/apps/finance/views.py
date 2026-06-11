from __future__ import annotations

from datetime import date

from django.db.models import F, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

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
    WalletAccountType,
    WalletEntry,
    WalletEntryType,
)
from .serializers import (
    AssetSerializer,
    BudgetSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    InvoicePaymentSerializer,
    InvoiceSerializer,
    TransactionCategorySerializer,
    TransactionSerializer,
    WalletEntrySerializer,
    WalletMovementSerializer,
    WalletSerializer,
    WalletTransferSerializer,
)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("category", "supplier", "recorded_by").all()
    serializer_class = ExpenseSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["category", "payment_method", "supplier"]
    search_fields = ["title", "reference", "notes"]
    ordering_fields = ["incurred_on", "amount", "created_at"]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("issued_by").all()
    serializer_class = InvoiceSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["status"]
    search_fields = ["invoice_number", "customer_name", "customer_email", "description"]
    ordering_fields = ["issue_date", "due_date", "amount", "created_at"]

    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue(self, request):
        qs = self.get_queryset().filter(
            Q(due_date__lt=date.today())
            & ~Q(status__in=[InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
        )
        page = self.paginate_queryset(qs)
        ser = self.get_serializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        serializer = InvoicePaymentSerializer(
            data=request.data, context={"invoice": invoice, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(InvoiceSerializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = InvoiceStatus.SENT
        invoice.save(update_fields=["status", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = InvoiceStatus.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)


class TransactionCategoryViewSet(viewsets.ModelViewSet):
    queryset = TransactionCategory.objects.all()
    serializer_class = TransactionCategorySerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["direction", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "direction", "created_at"]


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.select_related("category", "recorded_by").all()
    serializer_class = TransactionSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["direction", "category", "payment_method"]
    search_fields = ["title", "counterparty", "reference", "notes"]
    ordering_fields = ["occurred_on", "amount", "created_at"]


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.select_related("category").all()
    serializer_class = BudgetSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["category", "month"]
    ordering_fields = ["month", "amount"]


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related(
        "supplier", "recorded_by", "linked_expense"
    ).all()
    serializer_class = AssetSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["category", "status", "supplier"]
    search_fields = ["name", "reference", "notes"]
    ordering_fields = ["purchase_date", "purchase_cost", "created_at"]

    @action(detail=True, methods=["post"], url_path="dispose")
    def dispose(self, request, pk=None):
        asset = self.get_object()
        asset.status = "disposed"
        asset.save(update_fields=["status", "updated_at"])
        return Response(AssetSerializer(asset).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        asset = self.get_object()
        asset.status = "active"
        asset.save(update_fields=["status", "updated_at"])
        return Response(AssetSerializer(asset).data)


def build_wallet_ledger(wallet, limit: int = 100) -> list[dict]:
    """Merge a wallet's manual entries and its linked money flows into one
    chronological list. Each item is normalised to a common shape with an
    explicit ``direction`` ('in' or 'out')."""
    from apps.sales.models import Sale

    from .models import CREDIT_ENTRY_TYPES, TransactionDirection

    items: list[dict] = []

    for e in wallet.entries.select_related("counterparty_wallet")[:limit]:
        items.append({
            "source": "manual",
            "id": str(e.id),
            "kind": e.entry_type,
            "kind_display": e.get_entry_type_display(),
            "occurred_on": e.occurred_on.isoformat(),
            "description": e.description or (
                e.counterparty_wallet.name if e.counterparty_wallet else ""
            ),
            "amount": str(e.amount),
            "direction": "in" if e.entry_type in CREDIT_ENTRY_TYPES else "out",
            "created_at": e.created_at.isoformat(),
        })

    for s in Sale.objects.filter(wallet=wallet).order_by("-occurred_at")[:limit]:
        items.append({
            "source": "sale",
            "id": str(s.id),
            "kind": "sale",
            "kind_display": "Sale",
            "occurred_on": s.occurred_at.date().isoformat(),
            "description": s.receipt_number + (
                f" · {s.customer_name}" if s.customer_name else ""
            ),
            "amount": str(s.total),
            "direction": "in",
            "created_at": s.created_at.isoformat(),
        })

    for t in wallet.transactions.all()[:limit]:
        is_income = t.direction == TransactionDirection.INCOME
        items.append({
            "source": "transaction",
            "id": str(t.id),
            "kind": t.direction,
            "kind_display": t.get_direction_display(),
            "occurred_on": t.occurred_on.isoformat(),
            "description": t.title,
            "amount": str(t.amount),
            "direction": "in" if is_income else "out",
            "created_at": t.created_at.isoformat(),
        })

    for x in wallet.expenses.all()[:limit]:
        items.append({
            "source": "expense",
            "id": str(x.id),
            "kind": "expense",
            "kind_display": "Expense",
            "occurred_on": x.incurred_on.isoformat(),
            "description": x.title,
            "amount": str(x.amount),
            "direction": "out",
            "created_at": x.created_at.isoformat(),
        })

    items.sort(key=lambda i: (i["occurred_on"], i["created_at"]), reverse=True)
    return items[:limit]


class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.select_related("recorded_by").all()
    serializer_class = WalletSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["account_type", "is_active"]
    search_fields = ["name", "institution", "account_number", "notes"]
    ordering_fields = ["name", "account_type", "opening_balance", "created_at"]

    @action(detail=False, methods=["get"], url_path="account-types")
    def account_types(self, request):
        return Response(
            [{"value": v, "label": label} for v, label in WalletAccountType.choices]
        )

    def _record_movement(self, request, entry_type):
        wallet = self.get_object()
        serializer = WalletMovementSerializer(
            data=request.data,
            context={"wallet": wallet, "entry_type": entry_type, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def deposit(self, request, pk=None):
        return self._record_movement(request, WalletEntryType.DEPOSIT)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        return self._record_movement(request, WalletEntryType.WITHDRAWAL)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        wallet = self.get_object()
        serializer = WalletTransferSerializer(
            data=request.data, context={"wallet": wallet, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def entries(self, request, pk=None):
        wallet = self.get_object()
        qs = wallet.entries.select_related(
            "counterparty_wallet", "recorded_by"
        ).all()
        page = self.paginate_queryset(qs)
        ser = WalletEntrySerializer(page if page is not None else qs, many=True)
        return (
            self.get_paginated_response(ser.data)
            if page is not None
            else Response(ser.data)
        )

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        """Unified, chronological view of every movement that touches this
        wallet — manual entries plus linked sales, expenses and transactions.
        Mirrors exactly what `current_balance` sums."""
        wallet = self.get_object()
        return Response(build_wallet_ledger(wallet, limit=100))


class WalletEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WalletEntry.objects.select_related(
        "wallet", "counterparty_wallet", "recorded_by"
    ).all()
    serializer_class = WalletEntrySerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["wallet", "entry_type"]
    search_fields = ["description", "reference", "notes"]
    ordering_fields = ["occurred_on", "amount", "created_at"]
