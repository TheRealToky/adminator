from django.contrib import admin

from .models import Account, AccountingPeriod, JournalEntry, JournalLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "subtype", "is_postable", "is_active")
    list_filter = ("type", "is_postable", "is_active")
    search_fields = ("code", "name", "description")
    ordering = ("code",)


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0
    autocomplete_fields = ("account",)
    readonly_fields = ("account", "debit", "credit", "memo", "wallet")
    can_delete = False


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "memo", "event", "source_type", "status", "is_system")
    list_filter = ("status", "is_system", "event", "source_type")
    search_fields = ("memo", "source_id")
    date_hierarchy = "date"
    inlines = [JournalLineInline]
    readonly_fields = (
        "date", "period", "memo", "source_type", "source_id", "event",
        "status", "reversal_of", "is_system", "created_by",
    )


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ("label", "start_date", "status", "closed_at")
    list_filter = ("status",)
    ordering = ("-start_date",)
