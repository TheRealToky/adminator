"""Finance: expenses, invoices, budgets."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class ExpenseCategory(BaseModel):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense categories"

    def __str__(self) -> str:
        return self.name


class Expense(BaseModel):
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    title = models.CharField(max_length=160)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    incurred_on = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(
        max_length=16,
        choices=[
            ("cash", "Cash"),
            ("mobile_money", "Mobile Money"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
        ],
        default="cash",
    )
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )

    class Meta:
        ordering = ["-incurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["-incurred_on"]),
            models.Index(fields=["category", "-incurred_on"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} — {self.amount}"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PARTIALLY_PAID = "partially_paid", "Partially paid"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"


class Invoice(BaseModel):
    """Outbound invoice (we billed a customer)."""

    invoice_number = models.CharField(max_length=32, unique=True)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    amount_paid = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoices",
    )

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        indexes = [
            models.Index(fields=["-issue_date"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"INV-{self.invoice_number} ({self.status})"

    @property
    def balance_due(self) -> Decimal:
        return max(Decimal("0"), self.amount - self.amount_paid)

    @property
    def is_overdue(self) -> bool:
        return (
            self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
            and self.due_date < date.today()
        )


class TransactionDirection(models.TextChoices):
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


class TransactionCategory(BaseModel):
    """Category for a manual transaction (income or expense bucket)."""

    name = models.CharField(max_length=80)
    direction = models.CharField(
        max_length=8, choices=TransactionDirection.choices,
        default=TransactionDirection.EXPENSE,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["direction", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "direction"],
                name="unique_tx_category_name_direction",
            ),
        ]
        verbose_name_plural = "transaction categories"

    def __str__(self) -> str:
        return f"{self.name} ({self.direction})"


class Transaction(BaseModel):
    """Manual income or expense entry."""

    direction = models.CharField(
        max_length=8, choices=TransactionDirection.choices,
        default=TransactionDirection.EXPENSE,
    )
    category = models.ForeignKey(
        TransactionCategory, on_delete=models.PROTECT, related_name="transactions"
    )
    title = models.CharField(max_length=160)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    occurred_on = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(
        max_length=16,
        choices=[
            ("cash", "Cash"),
            ("mobile_money", "Mobile Money"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
        ],
        default="cash",
    )
    counterparty = models.CharField(
        max_length=160, blank=True,
        help_text="Free-form: customer for income, supplier for expense.",
    )
    reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    class Meta:
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["-occurred_on"]),
            models.Index(fields=["direction", "-occurred_on"]),
            models.Index(fields=["category", "-occurred_on"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} — {self.direction} {self.amount}"


class Budget(BaseModel):
    """Monthly budget per expense category."""

    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.CASCADE, related_name="budgets"
    )
    month = models.DateField(help_text="First day of the month this budget covers.")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-month", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "month"], name="unique_budget_per_category_month"
            )
        ]

    def __str__(self) -> str:
        return f"{self.category.name} · {self.month:%Y-%m}: {self.amount}"
