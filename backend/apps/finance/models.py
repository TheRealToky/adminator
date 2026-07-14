"""Finance: expenses, invoices, budgets."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
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
    on_credit = models.BooleanField(
        default=False,
        help_text=(
            "Supplier bill bought on credit: the expense is recognized now but "
            "credits Accounts Payable instead of a wallet until it is settled."
        ),
    )
    settled_at = models.DateField(
        null=True,
        blank=True,
        help_text="When an on-credit bill was paid. Drives the A/P settlement entry.",
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
    wallet = models.ForeignKey(
        "finance.Wallet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        help_text="Wallet the money was paid out of. Drives that wallet's balance.",
    )

    @property
    def is_outstanding_bill(self) -> bool:
        """An on-credit supplier bill that has not been settled yet (open A/P)."""
        return self.on_credit and self.settled_at is None

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
    wallet = models.ForeignKey(
        "finance.Wallet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        help_text="Wallet the money moved through. Drives that wallet's balance.",
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


class AssetCategory(models.TextChoices):
    EQUIPMENT = "equipment", "Equipment"
    FURNITURE = "furniture", "Furniture"
    VEHICLE = "vehicle", "Vehicle"
    ELECTRONICS = "electronics", "Electronics"
    FIT_OUT = "fit_out", "Shop fit-out"
    OTHER = "other", "Other"


class AssetStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DISPOSED = "disposed", "Disposed"


class Asset(BaseModel):
    """A capital asset other than ingredients or finished-product stock.

    Tracks ovens, mixers, fridges, vehicles, fittings, etc. Straight-line
    depreciation is computed on the fly from `useful_life_months` so the
    register stays simple — no GL, no journals, just a carrying value.
    """

    name = models.CharField(max_length=160)
    category = models.CharField(
        max_length=20,
        choices=AssetCategory.choices,
        default=AssetCategory.EQUIPMENT,
    )
    purchase_date = models.DateField(default=timezone.localdate)
    purchase_cost = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    useful_life_months = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Months over which to straight-line depreciate. Leave blank for no depreciation.",
    )
    status = models.CharField(
        max_length=10,
        choices=AssetStatus.choices,
        default=AssetStatus.ACTIVE,
    )
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    reference = models.CharField(
        max_length=80, blank=True,
        help_text="Invoice / receipt number.",
    )
    notes = models.TextField(blank=True)
    linked_expense = models.OneToOneField(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset",
        help_text="Optional Expense row created at purchase time so cash-out shows in P&L.",
    )
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )

    class Meta:
        ordering = ["-purchase_date", "-created_at"]
        indexes = [
            models.Index(fields=["-purchase_date"]),
            models.Index(fields=["category", "-purchase_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_category_display()})"

    # ── Straight-line depreciation, computed on the fly ─────────────────
    @property
    def months_elapsed(self) -> int:
        """Whole months between purchase date and today."""
        today = timezone.localdate()
        months = (today.year - self.purchase_date.year) * 12 + (
            today.month - self.purchase_date.month
        )
        if today.day < self.purchase_date.day:
            months -= 1
        return max(0, months)

    @property
    def accumulated_depreciation(self) -> Decimal:
        if self.status == AssetStatus.DISPOSED:
            return self.purchase_cost
        if not self.useful_life_months:
            return Decimal("0")
        elapsed = min(self.months_elapsed, self.useful_life_months)
        per_month = self.purchase_cost / Decimal(self.useful_life_months)
        return (per_month * Decimal(elapsed)).quantize(Decimal("0.01"))

    @property
    def carrying_value(self) -> Decimal:
        if self.status == AssetStatus.DISPOSED:
            return Decimal("0")
        return max(Decimal("0"), self.purchase_cost - self.accumulated_depreciation)

    @property
    def is_fully_depreciated(self) -> bool:
        if not self.useful_life_months:
            return False
        return self.months_elapsed >= self.useful_life_months


class WalletAccountType(models.TextChoices):
    CASH = "cash", "Cash"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    BANK = "bank", "Bank Account"
    CARD = "card", "Card"
    OTHER = "other", "Other"


class Wallet(BaseModel):
    """A place the business actually holds money — a cash drawer, a mobile-money
    line, a bank account, etc.

    The running balance is the ``opening_balance`` plus the signed sum of every
    ledger entry (deposits/transfers-in add, withdrawals/transfers-out subtract).
    Deliberately simple — no GL, no reconciliation engine, just a register the
    owner can keep current by hand.
    """

    name = models.CharField(max_length=120, unique=True)
    account_type = models.CharField(
        max_length=16,
        choices=WalletAccountType.choices,
        default=WalletAccountType.CASH,
    )
    opening_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Balance on the day this wallet started being tracked.",
    )
    institution = models.CharField(
        max_length=120, blank=True,
        help_text="Bank or provider name, e.g. 'Bank of Kigali', 'MTN MoMo'.",
    )
    account_number = models.CharField(
        max_length=64, blank=True,
        help_text="Account number or phone line — store masked if sensitive.",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallets",
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["account_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def current_balance(self) -> Decimal:
        """Opening balance, the manual ledger, and every money flow tagged to
        this wallet (sales in; expenses out; transactions either way)."""
        from apps.sales.models import Sale

        z = Decimal("0")
        entries = self.entries.aggregate(
            credit=Sum("amount", filter=Q(entry_type__in=CREDIT_ENTRY_TYPES)),
            debit=Sum("amount", filter=Q(entry_type__in=DEBIT_ENTRY_TYPES)),
        )
        sales_in = Sale.objects.filter(wallet=self).aggregate(s=Sum("total"))["s"] or z
        tx = self.transactions.aggregate(
            inc=Sum("amount", filter=Q(direction=TransactionDirection.INCOME)),
            exp=Sum("amount", filter=Q(direction=TransactionDirection.EXPENSE)),
        )
        expenses_out = self.expenses.aggregate(e=Sum("amount"))["e"] or z

        total = (
            self.opening_balance
            + (entries["credit"] or z)
            - (entries["debit"] or z)
            + sales_in
            + (tx["inc"] or z)
            - (tx["exp"] or z)
            - expenses_out
        )
        return total.quantize(Decimal("0.01"))


class WalletEntryType(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    WITHDRAWAL = "withdrawal", "Withdrawal"
    TRANSFER_IN = "transfer_in", "Transfer in"
    TRANSFER_OUT = "transfer_out", "Transfer out"


# Entry types that increase / decrease a wallet's balance.
CREDIT_ENTRY_TYPES = (WalletEntryType.DEPOSIT, WalletEntryType.TRANSFER_IN)
DEBIT_ENTRY_TYPES = (WalletEntryType.WITHDRAWAL, WalletEntryType.TRANSFER_OUT)


class WalletEntry(BaseModel):
    """A single money movement against a wallet.

    Deposits and withdrawals are standalone. Transfers create two linked rows —
    a ``transfer_out`` on the source and a ``transfer_in`` on the destination —
    sharing a ``transfer_group`` so the pair can be traced (and deleted) together.
    """

    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="entries"
    )
    entry_type = models.CharField(max_length=16, choices=WalletEntryType.choices)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    occurred_on = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=160, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    counterparty_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counterparty_entries",
        help_text="The other wallet involved, for transfers.",
    )
    transfer_group = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Shared by the two rows of a single transfer.",
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_entries",
    )

    class Meta:
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["wallet", "-occurred_on"]),
            models.Index(fields=["entry_type"]),
        ]
        verbose_name_plural = "wallet entries"

    def __str__(self) -> str:
        return f"{self.get_entry_type_display()} {self.amount} · {self.wallet_id}"

    @property
    def signed_amount(self) -> Decimal:
        if self.entry_type in DEBIT_ENTRY_TYPES:
            return -self.amount
        return self.amount
