from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import status as http_status

from apps.core.permissions import IsManagerOrAdmin, ReadOnlyOrManager

from . import reports
from .models import Account, AccountingPeriod, JournalEntry, PeriodStatus
from .posting import Leg, LedgerError, post
from .serializers import (
    AccountingPeriodSerializer,
    AccountSerializer,
    JournalEntrySerializer,
    ManualJournalEntrySerializer,
)


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """The chart of accounts (read-only over the API; managed via seed/admin)."""

    queryset = Account.objects.select_related("parent").all()
    serializer_class = AccountSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["type", "subtype", "is_active", "is_postable"]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["code", "name", "type"]


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        JournalEntry.objects.select_related("period", "created_by")
        .prefetch_related("lines__account")
        .all()
    )
    serializer_class = JournalEntrySerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["status", "event", "source_type", "is_system", "period"]
    search_fields = ["memo", "source_id"]
    ordering_fields = ["date", "created_at"]

    @action(detail=False, methods=["post"], url_path="manual",
            permission_classes=[IsManagerOrAdmin])
    def manual(self, request):
        """Create a hand-entered, balanced journal entry (non-system)."""
        serializer = ManualJournalEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        legs = [
            Leg(account=line["account"], debit=line.get("debit"),
                credit=line.get("credit"), memo=line.get("memo", ""))
            for line in data["lines"]
        ]
        try:
            entry = post(
                date=data["date"], legs=legs, memo=data.get("memo", ""),
                is_system=False, created_by=request.user,
            )
        except LedgerError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(
            JournalEntrySerializer(entry).data, status=http_status.HTTP_201_CREATED
        )


class AccountingPeriodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AccountingPeriod.objects.all()
    serializer_class = AccountingPeriodSerializer
    permission_classes = [ReadOnlyOrManager]
    filterset_fields = ["status"]

    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def close(self, request, pk=None):
        """Close a period: no further postings may target it."""
        period = self.get_object()
        period.status = PeriodStatus.CLOSED
        period.closed_at = timezone.now()
        period.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(AccountingPeriodSerializer(period).data)

    @action(detail=True, methods=["post"], permission_classes=[IsManagerOrAdmin])
    def reopen(self, request, pk=None):
        period = self.get_object()
        period.status = PeriodStatus.OPEN
        period.closed_at = None
        period.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(AccountingPeriodSerializer(period).data)


class TrialBalanceView(APIView):
    permission_classes = [ReadOnlyOrManager]

    def get(self, request):
        as_of = _parse_date(request.query_params.get("as_of"), timezone.localdate())
        return Response(reports.trial_balance(as_of=as_of))


class IncomeStatementView(APIView):
    permission_classes = [ReadOnlyOrManager]

    def get(self, request):
        end = _parse_date(request.query_params.get("end"), timezone.localdate())
        start = _parse_date(
            request.query_params.get("start"), end - timedelta(days=30)
        )
        return Response(reports.income_statement(start=start, end=end))


class BalanceSheetView(APIView):
    permission_classes = [ReadOnlyOrManager]

    def get(self, request):
        as_of = _parse_date(request.query_params.get("as_of"), timezone.localdate())
        return Response(reports.balance_sheet(as_of=as_of))
