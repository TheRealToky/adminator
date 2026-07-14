"""The posting engine: turn a set of balanced legs into a JournalEntry.

Everything that writes to the ledger goes through :func:`post` or
:func:`post_source`. These enforce the core invariants (balanced, valid period)
and make source-driven posting idempotent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import (
    ZERO,
    Account,
    AccountingPeriod,
    EntryStatus,
    JournalEntry,
    JournalLine,
)

logger = logging.getLogger("apps.ledger")


class LedgerError(Exception):
    """Raised when a would-be posting is invalid (unbalanced, closed period …)."""


@dataclass
class Leg:
    """One side of an entry. Exactly one of ``debit``/``credit`` is non-zero."""

    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    memo: str = ""
    wallet: object | None = None

    @staticmethod
    def dr(account: Account, amount, memo: str = "", wallet=None) -> "Leg":
        return Leg(account=account, debit=Decimal(amount), memo=memo, wallet=wallet)

    @staticmethod
    def cr(account: Account, amount, memo: str = "", wallet=None) -> "Leg":
        return Leg(account=account, credit=Decimal(amount), memo=memo, wallet=wallet)


def _validate(legs: list[Leg]) -> None:
    if len(legs) < 2:
        raise LedgerError("A journal entry needs at least two legs.")
    total_debit = sum((l.debit for l in legs), ZERO)
    total_credit = sum((l.credit for l in legs), ZERO)
    for leg in legs:
        if leg.debit < ZERO or leg.credit < ZERO:
            raise LedgerError("Journal legs cannot be negative.")
        if leg.debit and leg.credit:
            raise LedgerError("A leg cannot be both a debit and a credit.")
        if not leg.debit and not leg.credit:
            raise LedgerError("A leg must have a non-zero debit or credit.")
    if total_debit != total_credit:
        raise LedgerError(
            f"Entry does not balance: debit {total_debit} != credit {total_credit}."
        )


@transaction.atomic
def post(
    *,
    date,
    legs: list[Leg],
    memo: str = "",
    source_type: str = "",
    source_id: str = "",
    event: str = "",
    is_system: bool = True,
    created_by=None,
) -> JournalEntry:
    """Create one balanced, posted :class:`JournalEntry`.

    Raises :class:`LedgerError` if the legs don't balance or the target period
    is not open.
    """
    _validate(legs)

    period = AccountingPeriod.for_date(date)
    if not period.is_postable:
        raise LedgerError(f"Period {period.label} is {period.status}; cannot post.")

    entry = JournalEntry.objects.create(
        date=date,
        period=period,
        memo=memo,
        source_type=source_type,
        source_id=str(source_id),
        event=event,
        is_system=is_system,
        created_by=created_by,
    )
    JournalLine.objects.bulk_create([
        JournalLine(
            entry=entry,
            account=leg.account,
            debit=leg.debit,
            credit=leg.credit,
            memo=leg.memo,
            wallet=leg.wallet,
        )
        for leg in legs
    ])
    return entry


def _unpost(entry: JournalEntry) -> None:
    """Remove/void a prior system entry so its source can be re-posted.

    In an OPEN period a regenerable system entry is simply deleted (kept tidy).
    In a CLOSED/LOCKED period history is immutable, so we mark it reversed and
    book an equal-and-opposite reversing entry in the current open period.
    """
    if entry.period.is_postable:
        entry.delete()
        return

    reversal = JournalEntry.objects.create(
        date=entry.date,
        period=AccountingPeriod.for_date(entry.date),  # will land in an open period
        memo=f"Reversal of {entry.memo or entry.event}",
        source_type=entry.source_type,
        source_id=entry.source_id,
        event=f"{entry.event}:reversal",
        is_system=True,
        reversal_of=entry,
    )
    JournalLine.objects.bulk_create([
        JournalLine(
            entry=reversal, account=l.account,
            debit=l.credit, credit=l.debit, memo=l.memo, wallet=l.wallet,
        )
        for l in entry.lines.all()
    ])
    entry.status = EntryStatus.REVERSED
    entry.save(update_fields=["status", "updated_at"])


@transaction.atomic
def post_source(
    *,
    source_type: str,
    source_id: str,
    event: str,
    date,
    legs: list[Leg],
    memo: str = "",
    created_by=None,
) -> JournalEntry:
    """Idempotently (re)post the entry for a domain source+event.

    Any existing live entry for ``(source_type, source_id, event)`` is unposted
    first, so calling this repeatedly always converges to a single correct entry.
    """
    existing = JournalEntry.objects.filter(
        source_type=source_type,
        source_id=str(source_id),
        event=event,
        status=EntryStatus.POSTED,
    ).first()
    if existing:
        _unpost(existing)

    return post(
        date=date, legs=legs, memo=memo,
        source_type=source_type, source_id=source_id, event=event,
        is_system=True, created_by=created_by,
    )


@transaction.atomic
def reverse_source(*, source_type: str, source_id: str, event: str | None = None) -> int:
    """Void the live entries for a source (used when a domain row is deleted).

    Returns the number of entries voided.
    """
    qs = JournalEntry.objects.filter(
        source_type=source_type, source_id=str(source_id), status=EntryStatus.POSTED
    )
    if event is not None:
        qs = qs.filter(event=event)
    count = 0
    for entry in qs:
        _unpost(entry)
        count += 1
    return count


# ── Shadow-mode wrappers ───────────────────────────────────────────────────
def posting_enabled() -> bool:
    return getattr(settings, "LEDGER_POSTING_ENABLED", True)


def shadow_mode() -> bool:
    """When true, a posting failure is logged but never propagated, so a ledger
    bug can never block an operational write (sale, expense …)."""
    return getattr(settings, "LEDGER_SHADOW_MODE", True)


def safe_post_source(**kwargs) -> JournalEntry | None:
    """Call :func:`post_source`, swallowing errors in shadow mode."""
    if not posting_enabled():
        return None
    try:
        return post_source(**kwargs)
    except Exception:  # noqa: BLE001 — shadow mode must not break the caller
        logger.exception("Ledger posting failed for %s", kwargs.get("source_type"))
        if not shadow_mode():
            raise
        return None


def safe_reverse_source(**kwargs) -> int:
    if not posting_enabled():
        return 0
    try:
        return reverse_source(**kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Ledger reversal failed for %s", kwargs.get("source_type"))
        if not shadow_mode():
            raise
        return 0
