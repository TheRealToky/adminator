"""Double-entry general ledger.

The ledger is the single source of truth for accrual-basis financial statements.
It is deliberately additive to the existing cash-derived aggregates: domain
events (a Sale, an Expense, a Transaction …) *post* balanced journal entries
here, and reports are built by summing accounts — not by re-scanning domain rows.

Design invariants:
  * Every ``JournalEntry`` balances: Σ debit == Σ credit.
  * Entries are append-only in *closed* periods; a correction is a reversing
    entry, never an in-place edit.
  * Auto-generated ("system") entries carry a ``source`` (type + id + event) so
    posting is idempotent — re-posting the same source replaces its prior entry
    while the period is still open.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.models import BaseModel

ZERO = Decimal("0")
MONEY = dict(max_digits=16, decimal_places=2)


class AccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity"
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


# Account types whose natural (normal) balance is on the debit side. Everything
# else is credit-normal. This single fact drives statement signing.
DEBIT_NORMAL_TYPES = (AccountType.ASSET, AccountType.EXPENSE)
BALANCE_SHEET_TYPES = (AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY)
INCOME_STATEMENT_TYPES = (AccountType.INCOME, AccountType.EXPENSE)


class Account(BaseModel):
    """A node in the chart of accounts.

    Leaf accounts (``is_postable=True``) receive journal lines; parent accounts
    exist only to subtotal on statements.
    """

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=12, choices=AccountType.choices)
    subtype = models.CharField(
        max_length=40, blank=True,
        help_text="Free-form grouping, e.g. 'current_asset', 'cogs', 'operating_expense'.",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children",
    )
    is_postable = models.BooleanField(
        default=True, help_text="Only leaf accounts may receive journal lines."
    )
    is_active = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, default="RWF")
    description = models.TextField(blank=True)

    # Optional links that let existing entities own a dedicated sub-account, so
    # per-wallet cash and per-category expense balances roll up automatically.
    wallet = models.OneToOneField(
        "finance.Wallet", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ledger_account",
    )
    expense_category = models.OneToOneField(
        "finance.ExpenseCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ledger_account",
    )

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    @property
    def is_debit_normal(self) -> bool:
        return self.type in DEBIT_NORMAL_TYPES

    @property
    def normal_balance(self) -> str:
        return "debit" if self.is_debit_normal else "credit"


class PeriodStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"      # no new postings; corrections reverse forward
    LOCKED = "locked", "Locked"      # hard freeze (e.g. filed with tax authority)


class AccountingPeriod(BaseModel):
    """A calendar month the books can be opened against and later closed.

    Periods are auto-created (OPEN) the first time something posts into their
    month, so day-to-day posting never has to think about them. Closing a period
    is an explicit action that blocks further postings into it.
    """

    start_date = models.DateField(unique=True, help_text="First day of the month.")
    label = models.CharField(max_length=20, help_text="e.g. '2026-07'.")
    status = models.CharField(
        max_length=8, choices=PeriodStatus.choices, default=PeriodStatus.OPEN
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.label} ({self.status})"

    @property
    def is_postable(self) -> bool:
        return self.status == PeriodStatus.OPEN

    @classmethod
    def for_date(cls, when) -> "AccountingPeriod":
        """Return (creating if needed) the OPEN period containing ``when``."""
        first = when.replace(day=1)
        period, _ = cls.objects.get_or_create(
            start_date=first, defaults={"label": f"{first:%Y-%m}"}
        )
        return period


class EntryStatus(models.TextChoices):
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"


class JournalEntry(BaseModel):
    """The header of a balanced double-entry transaction."""

    date = models.DateField(
        default=timezone.localdate,
        help_text="Accounting date — when the event is recognized, not created_at.",
    )
    period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, related_name="entries"
    )
    memo = models.CharField(max_length=240, blank=True)

    # Idempotency / traceability back to the domain row that generated this.
    source_type = models.CharField(
        max_length=64, blank=True,
        help_text="Domain model label, e.g. 'sales.Sale'. Blank for manual entries.",
    )
    source_id = models.CharField(max_length=64, blank=True)
    event = models.CharField(
        max_length=40, blank=True,
        help_text="Distinguishes multiple entries per source, e.g. 'revenue', 'cogs'.",
    )

    status = models.CharField(
        max_length=10, choices=EntryStatus.choices, default=EntryStatus.POSTED
    )
    reversal_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reversed_by_entries",
    )
    is_system = models.BooleanField(
        default=True, help_text="Auto-posted from a domain event vs. entered by hand."
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="journal_entries",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["-date"]),
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            # At most one live (posted) system entry per (source, event).
            models.UniqueConstraint(
                fields=["source_type", "source_id", "event"],
                condition=Q(status="posted") & ~Q(source_type=""),
                name="unique_live_entry_per_source_event",
            ),
        ]

    def __str__(self) -> str:
        return f"JE {self.date} {self.memo or self.event or ''}".strip()

    @property
    def total_debit(self) -> Decimal:
        return self.lines.aggregate(s=Sum("debit"))["s"] or ZERO

    @property
    def total_credit(self) -> Decimal:
        return self.lines.aggregate(s=Sum("credit"))["s"] or ZERO

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class JournalLine(BaseModel):
    """One leg of a journal entry — a debit or a credit to a single account."""

    entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="lines"
    )
    debit = models.DecimalField(default=ZERO, validators=[MinValueValidator(ZERO)], **MONEY)
    credit = models.DecimalField(default=ZERO, validators=[MinValueValidator(ZERO)], **MONEY)
    memo = models.CharField(max_length=240, blank=True)

    # Optional analysis dimension: which wallet this cash leg belongs to.
    wallet = models.ForeignKey(
        "finance.Wallet", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ledger_lines",
    )

    class Meta:
        ordering = ["entry", "created_at"]
        indexes = [
            models.Index(fields=["account"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="journal_line_one_side_only",
                condition=Q(debit=ZERO) | Q(credit=ZERO),
            ),
            models.CheckConstraint(
                name="journal_line_non_negative",
                condition=Q(debit__gte=ZERO) & Q(credit__gte=ZERO),
            ),
        ]

    def __str__(self) -> str:
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.account.code} {side}"

    @property
    def signed_amount(self) -> Decimal:
        """debit − credit (positive = increases a debit-normal account)."""
        return self.debit - self.credit
