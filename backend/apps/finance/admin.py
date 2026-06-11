from django.contrib import admin

from .models import (
    Asset,
    Budget,
    Expense,
    ExpenseCategory,
    Invoice,
    Transaction,
    TransactionCategory,
    Wallet,
    WalletEntry,
)


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


@admin.register(TransactionCategory)
class TransactionCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "direction", "is_active")
    list_filter = ("direction", "is_active")
    search_fields = ("name",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("title", "direction", "category", "amount", "occurred_on", "payment_method")
    list_filter = ("direction", "category", "payment_method", "occurred_on")
    search_fields = ("title", "counterparty", "reference", "notes")
    autocomplete_fields = ("category", "recorded_by")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "purchase_date", "purchase_cost",
        "useful_life_months", "status", "supplier",
    )
    list_filter = ("category", "status", "purchase_date")
    search_fields = ("name", "reference", "notes")
    autocomplete_fields = ("supplier", "recorded_by", "linked_expense")
    readonly_fields = ("months_elapsed", "accumulated_depreciation", "carrying_value")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "name", "account_type", "opening_balance", "current_balance",
        "institution", "is_active",
    )
    list_filter = ("account_type", "is_active")
    search_fields = ("name", "institution", "account_number", "notes")
    readonly_fields = ("current_balance",)

    @admin.display(description="Current balance")
    def current_balance(self, obj):
        return obj.current_balance


@admin.register(WalletEntry)
class WalletEntryAdmin(admin.ModelAdmin):
    list_display = (
        "wallet", "entry_type", "amount", "occurred_on",
        "counterparty_wallet", "reference",
    )
    list_filter = ("entry_type", "occurred_on")
    search_fields = ("description", "reference", "notes")
    autocomplete_fields = ("wallet", "counterparty_wallet", "recorded_by")
