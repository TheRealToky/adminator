"""Production runs — bake N units of product P on day D."""
from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class ProductionStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class ProductionRun(BaseModel):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="production_runs"
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Number of product units produced (or planned).",
    )
    status = models.CharField(
        max_length=12, choices=ProductionStatus.choices, default=ProductionStatus.COMPLETED
    )
    scheduled_for = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        help_text="Auto-computed: sum(recipe quantity × material unit_cost) × quantity.",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="production_runs",
    )

    class Meta:
        ordering = ["-scheduled_for", "-created_at"]
        indexes = [
            models.Index(fields=["-scheduled_for"]),
            models.Index(fields=["product", "-scheduled_for"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity} on {self.scheduled_for}"
