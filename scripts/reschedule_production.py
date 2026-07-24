#!/usr/bin/env python3
r"""Reschedule production runs: move ``scheduled_for`` 2026-07-20 → 2026-07-21,
but *only* for runs that were **completed** on 2026-07-23.

Background
----------
Some runs were baked/recorded against the wrong business date. This script
retags them from one ``scheduled_for`` date to another. It is a **pure metadata
update**: ``scheduled_for`` is only a label for the bake/business day and has no
bearing on inventory. The raw materials consumed and the finished units produced
are unaffected — so, unlike ``delete_sales_production.py``, there is *no* stock
movement to mirror or reverse here. Only the date field changes.

Scope guard — *nothing less, nothing more*
------------------------------------------
A run is retagged **iff** all of the following hold:
  * ``scheduled_for`` == ``--from-date``      (default 2026-07-20), AND
  * ``status`` == ``completed``, AND
  * ``completed_at`` falls on ``--completed-date`` (default 2026-07-23) in the
    business timezone (default Africa/Kigali).

``completed_at`` is stored in UTC, so "completed on the 23rd" is evaluated
against the **local** (Kigali) calendar day: a run completed at 23:30 UTC on the
22nd (= 01:30 Kigali on the 23rd) counts as the 23rd, matching how
``delete_sales_production.py`` keys its business day. Planned/cancelled runs have
no ``completed_at`` and are never touched.

Safe by default: runs in **dry-run** mode (prints the full plan, writes nothing).
Pass ``--commit`` to actually update. The whole commit runs in one transaction —
any error rolls the entire thing back.

Run it INSIDE the backend container (it needs Django + the DB), e.g.:

    # dry-run preview (no writes):
    docker exec -i adminator-scratch-backend python - < scripts/reschedule_production.py

    # actually reschedule:
    docker exec -i adminator-scratch-backend python - --commit < scripts/reschedule_production.py

    # different dates / timezone:
    docker exec -i adminator-scratch-backend python - --commit \
        --from-date 2026-07-20 --to-date 2026-07-21 \
        --completed-date 2026-07-23 --tz Africa/Kigali \
        < scripts/reschedule_production.py
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore


# ── Django bootstrap ─────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.production.models import ProductionRun, ProductionStatus  # noqa: E402


DEFAULT_FROM_DATE = "2026-07-20"
DEFAULT_TO_DATE = "2026-07-21"
DEFAULT_COMPLETED_DATE = "2026-07-23"
DEFAULT_TZ = os.environ.get("BUSINESS_TIMEZONE", "Africa/Kigali")


class DryRunRollback(Exception):
    """Raised at the end of a dry-run to roll the transaction back."""


# ── selection ────────────────────────────────────────────────────────────────
def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) aware datetimes spanning `day` in the business timezone."""
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = datetime.fromordinal(day.toordinal() + 1)
    end = datetime(end.year, end.month, end.day, tzinfo=tz)
    return start, end


def select(from_day: date, completed_day: date, tz: ZoneInfo):
    """Completed runs scheduled on `from_day` whose completed_at is on `completed_day`."""
    start, end = local_day_bounds(completed_day, tz)
    return (
        ProductionRun.objects.filter(
            scheduled_for=from_day,
            status=ProductionStatus.COMPLETED,
            completed_at__gte=start,
            completed_at__lt=end,
        )
        .select_related("product")
        .order_by("completed_at")
    )


# ── main ─────────────────────────────────────────────────────────────────────
def run(from_day: date, to_day: date, completed_day: date, tz: ZoneInfo, commit: bool) -> int:
    mode = "COMMIT" if commit else "DRY-RUN (no writes)"
    print(f"Reschedule production · {mode}")
    print(f"  scheduled_for : {from_day} → {to_day}")
    print(f"  guard         : status=completed AND completed_at on {completed_day} ({tz.key})\n")

    runs = list(select(from_day, completed_day, tz))
    print(f"Selected : {len(runs)} run(s) to reschedule\n")

    if not runs:
        print("Nothing matches — no runs rescheduled.")
        return 0

    try:
        with transaction.atomic():
            for r in runs:
                completed_local = r.completed_at.astimezone(tz)
                print(
                    f"  {r.product.name} ×{r.quantity}  (run {str(r.id)[:8]}, "
                    f"completed {completed_local:%Y-%m-%d %H:%M} {tz.key})  "
                    f"scheduled_for {r.scheduled_for} → {to_day}"
                )
                if commit:
                    r.scheduled_for = to_day
                    r.save(update_fields=["scheduled_for", "updated_at"])

            if not commit:
                raise DryRunRollback
    except DryRunRollback:
        print("\n" + "=" * 60)
        print("DRY-RUN — transaction rolled back, nothing written.")
        print("Re-run with --commit to actually reschedule.")
        return 0

    print("\n" + "=" * 60)
    print("DONE — committed.")
    print(f"  runs rescheduled : {len(runs)}  ({from_day} → {to_day})")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-date", default=DEFAULT_FROM_DATE,
                   help=f"Current scheduled_for to change from (default {DEFAULT_FROM_DATE}).")
    p.add_argument("--to-date", default=DEFAULT_TO_DATE,
                   help=f"New scheduled_for to set (default {DEFAULT_TO_DATE}).")
    p.add_argument("--completed-date", default=DEFAULT_COMPLETED_DATE,
                   help=f"Only runs completed on this business day (default {DEFAULT_COMPLETED_DATE}).")
    p.add_argument("--tz", default=DEFAULT_TZ, help=f"Business timezone (default {DEFAULT_TZ}).")
    p.add_argument("--commit", action="store_true", help="Actually update (default: dry-run).")
    args = p.parse_args()

    from_day = date.fromisoformat(args.from_date)
    to_day = date.fromisoformat(args.to_date)
    completed_day = date.fromisoformat(args.completed_date)
    tz = ZoneInfo(args.tz)
    return run(from_day, to_day, completed_day, tz, args.commit)


if __name__ == "__main__":
    sys.exit(main())
