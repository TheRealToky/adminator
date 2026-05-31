from django.urls import path

from .views import (
    BusyHoursView,
    DashboardOverviewView,
    ExpenseBreakdownView,
    ForecastView,
    InventoryOnHandView,
    ProductionSummaryView,
    SalesTimeseriesView,
    StockHealthView,
    TopProductsView,
)

urlpatterns = [
    path("dashboard/", DashboardOverviewView.as_view(), name="dashboard"),
    path("sales-timeseries/", SalesTimeseriesView.as_view(), name="sales-timeseries"),
    path("busy-hours/", BusyHoursView.as_view(), name="busy-hours"),
    path("top-products/", TopProductsView.as_view(), name="top-products"),
    path("stock-health/", StockHealthView.as_view(), name="stock-health"),
    path("inventory-on-hand/", InventoryOnHandView.as_view(), name="inventory-on-hand"),
    path("production-summary/", ProductionSummaryView.as_view(), name="production-summary"),
    path("expense-breakdown/", ExpenseBreakdownView.as_view(), name="expense-breakdown"),
    path("forecast/", ForecastView.as_view(), name="forecast"),
]
