from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    BudgetViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    InvoiceViewSet,
    TransactionCategoryViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("budgets", BudgetViewSet, basename="budget")
router.register("transaction-categories", TransactionCategoryViewSet, basename="transaction-category")
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("assets", AssetViewSet, basename="asset")

urlpatterns = router.urls
