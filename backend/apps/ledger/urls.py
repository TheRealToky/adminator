from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountingPeriodViewSet,
    AccountViewSet,
    BalanceSheetView,
    IncomeStatementView,
    JournalEntryViewSet,
    TrialBalanceView,
)

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("journal-entries", JournalEntryViewSet, basename="journal-entry")
router.register("periods", AccountingPeriodViewSet, basename="accounting-period")

urlpatterns = router.urls + [
    path("reports/trial-balance/", TrialBalanceView.as_view(), name="trial-balance"),
    path("reports/income-statement/", IncomeStatementView.as_view(), name="income-statement"),
    path("reports/balance-sheet/", BalanceSheetView.as_view(), name="balance-sheet"),
]
