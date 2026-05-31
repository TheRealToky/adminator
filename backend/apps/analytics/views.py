from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


def _days_param(request, default: int = 30, maximum: int = 365) -> int:
    raw = request.query_params.get("days", default)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = default
    return max(1, min(days, maximum))


class DashboardOverviewView(APIView):
    """All the dashboard widgets in one round-trip."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = _days_param(request)
        return Response({
            "kpis": services.kpi_summary(days=days),
            "sales_timeseries": services.sales_timeseries(days=days),
            "busy_hours": services.busy_hours(days=days),
            "top_products": services.top_products(days=days),
            "payment_mix": services.payment_mix(days=days),
            "stock_health": services.stock_health(),
            "inventory": services.inventory_on_hand_value(),
            "production_summary": services.production_summary(days=days),
            "expense_breakdown": services.expense_breakdown(days=days),
            "invoices": services.invoices_status_breakdown(),
        })


class SalesTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.sales_timeseries(days=_days_param(request)))


class BusyHoursView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.busy_hours(days=_days_param(request)))


class TopProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        return Response(services.top_products(days=_days_param(request), limit=limit))


class StockHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.stock_health())


class InventoryOnHandView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.inventory_on_hand_value())


class ProductionSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.production_summary(days=_days_param(request)))


class ExpenseBreakdownView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.expense_breakdown(days=_days_param(request)))


class ForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = _days_param(request, default=60)
        horizon = max(1, min(int(request.query_params.get("horizon", 14)), 60))
        return Response(services.naive_sales_forecast(
            history_days=history, forecast_days=horizon
        ))
