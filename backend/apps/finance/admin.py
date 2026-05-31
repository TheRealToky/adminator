from django.contrib import admin

from .models import Budget, Expense, ExpenseCategory, Invoice


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "amount", "incurred_on", "payment_method", "supplier")
    list_filter = ("category", "payment_method", "incurred_on")
    search_fields = ("title", "reference", "notes")
    autocomplete_fields = ("category", "supplier", "recorded_by")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "customer_name", "amount",
                    "amount_paid", "status", "issue_date", "due_date")
    list_filter = ("status", "issue_date", "due_date")
    search_fields = ("invoice_number", "customer_name", "customer_email")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("category", "month", "amount")
    list_filter = ("category", "month")
    autocomplete_fields = ("category",)
