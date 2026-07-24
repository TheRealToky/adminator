#!/usr/bin/env python3
r"""Delete a single day's SALES, returning the sold items to finished-goods stock.

For the target business day (default **2026-07-21**, Africa/Kigali) this script
deletes every sale whose ``occurred_at`` falls on that local date, using the
app's own :func:`apps.sales.services.delete_sale`.

What that does — and deliberately all it does:
  * each sold line item's quantity is **added back to that product's finished-
    goods stock** (an inventory movement with reason ``RETURN``),
  * the ``Sale`` and its ``SaleItem`` rows are removed (wallet balances are
    derived, so they self-correct).

A sale only ever draws down **finished-product** stock, so nothing here touches
raw materials or processed materials — the returned item goes back to inventory
as the finished product it was sold as, nothing more.

This is the sales-only counterpart to ``delete_sales_production.py``: it does
**not** delete or reverse any production run.

Scope guard — *nothing less, nothing more*: sales are keyed on the **local**
(Kigali) date of ``occurred_at``, so a sale at 23:30 UTC on the 20th
(= 01:30 Kigali on the 21st) counts as the 21st.

Safe by default: runs in **dry-run** mode (prints the full plan, writes nothing).
Pass ``--commit`` to actually delete. The whole commit runs in one transaction —
any error rolls the entire thing back.

Run it INSIDE the backend container (it needs Django + the DB), e.g.:

    # dry-run preview (no writes):
    docker exec -i adminator-scratch-backend python - < scripts/delete_sales_only.py

    # actually delete + restore stock:
    docker exec -i adminator-scratch-backend python - --commit < scripts/delete_sales_only.py

    # a different day:
    docker exec -i adminator-scratch-backend python - --date 2026-07-21 --commit \
        < scripts/delete_sales_only.py
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from decimal import Decimal

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore


# ── Django bootstrap ─────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.sales import services as sales_services  # noqa: E402
from apps.sales.models import Sale  # noqa: E402


DEFAULT_DATE = "2026-07-21"
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


def select_sales(day: date, tz: ZoneInfo):
    start, end = local_day_bounds(day, tz)
    return (
        Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .prefetch_related("items__product")
        .order_by("occurred_at")
    )


# ── main ─────────────────────────────────────────────────────────────────────
def run(day: date, tz: ZoneInfo, commit: bool) -> int:
    apply = commit
    mode = "COMMIT" if commit else "DRY-RUN (no writes)"
    print(f"Delete sales (return items to finished-goods stock) · {mode}")
    print(f"Business day : {day}  ({tz.key})")

    sales = list(select_sales(day, tz))
    n_items = sum(s.items.count() for s in sales)
    sales_total = sum((s.total for s in sales), Decimal("0"))
    print(f"Selected     : {len(sales)} sales ({n_items} line items, total {sales_total})\n")

    if not sales:
        print("No sales to delete for this day.")
        return 0

    try:
        with transaction.atomic():
            print("SALES")
            for s in sales:
                print(
                    f"  #{s.receipt_number}  {s.occurred_at:%Y-%m-%d %H:%M}Z  "
                    f"total {s.total}  ({s.items.count()} items) — delete + restore stock"
                )
                for item in s.items.all():
                    print(f"    ↩ +{item.quantity}  {item.product.name} (finished stock)")
                if apply:
                    sales_services.delete_sale(sale=s)

            if not commit:
                raise DryRunRollback
    except DryRunRollback:
        print("\n" + "=" * 60)
        print("DRY-RUN — transaction rolled back, nothing written.")
        print("Re-run with --commit to actually delete + restore stock.")
        return 0

    print("\n" + "=" * 60)
    print("DONE — committed.")
    print(f"  sales deleted        : {len(sales)}")
    print(f"  line items returned  : {n_items}")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=DEFAULT_DATE, help="Business day YYYY-MM-DD (default 2026-07-21).")
    p.add_argument("--tz", default=DEFAULT_TZ, help=f"Business timezone (default {DEFAULT_TZ}).")
    p.add_argument("--commit", action="store_true", help="Actually delete (default: dry-run).")
    args = p.parse_args()

    day = date.fromisoformat(args.date)
    tz = ZoneInfo(args.tz)
    return run(day, tz, args.commit)


if __name__ == "__main__":
    sys.exit(main())
