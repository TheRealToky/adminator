"""Abstract building blocks reused across every app."""
from __future__ import annotations

import uuid

from django.db import models


class TimestampedModel(models.Model):
    """Adds created_at / updated_at to any model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """Use opaque UUIDs as primary keys for resources exposed via the API."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimestampedModel):
    """The standard base for first-class domain entities."""

    class Meta:
        abstract = True
