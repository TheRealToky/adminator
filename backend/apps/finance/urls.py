from rest_framework.routers import DefaultRouter

from .views import BudgetViewSet, ExpenseCategoryViewSet, ExpenseViewSet, InvoiceViewSet

router = DefaultRouter()
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("budgets", BudgetViewSet, basename="budget")

urlpatterns = router.urls
