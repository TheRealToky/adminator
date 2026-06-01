from __future__ import annotations

from datetime import date

from django.db.models import F, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import ReadOnlyOrManager

from .models import (
    Budget,
    Expense,
    ExpenseCategory,
    Invoice,
    InvoiceStatus,
    Transaction,
    TransactionCategory,
)
from .serializers import (
    BudgetSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    InvoicePaymentSerializer,
    InvoiceSerializer,
    TransactionCategorySerializer,
    TransactionSerializer,
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
