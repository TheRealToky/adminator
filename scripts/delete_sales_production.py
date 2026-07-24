#!/usr/bin/env python3
r"""Delete a single day's SALES and PRODUCTION, fully reversing their inventory.

For the target business day (default **2026-07-21**, Africa/Kigali) this script:

1. **Deletes every sale** whose ``occurred_at`` falls on that local date, using
   the app's own :func:`apps.sales.services.delete_sale`. That restores the sold
   finished-product units back onto stock (reason ``RETURN``) and removes the
   receipt + its line items. Wallet balances are derived, so they self-correct.

2. **Reverses and deletes every completed production run** whose
   ``scheduled_for`` equals that date. Reversal mirrors
   :func:`apps.production.services.execute_production` exactly, in reverse:
       * each recipe **raw material** is returned to the raw-materials inventory
         (``item.quantity × run.quantity``),
       * each **processed material** the product uses is returned to the
         processed-materials inventory (``usage.quantity × run.quantity``),
       * the finished-product **output** (``run.quantity``) is removed from stock,
       * the ``ProductionRun`` row is deleted.
   (Deleting a run does *not* reverse stock on its own — hence this script.)

Net effect ("full reversal"): inventory, sales and production return to the
state they were in at the start of that day, as if it never happened.

Scope guards — *nothing less, nothing more*:
  * Sales are keyed on the **local** (Kigali) date of ``occurred_at``, so a sale
    at 23:30 UTC on the 20th (= 01:30 Kigali on the 21st) counts as the 21st.
  * Production is keyed on ``scheduled_for`` (the bake/business date), matching
    how ``import_production.py`` records runs.
  * Only ``completed`` runs moved stock, so only those are stock-reversed;
    planned/cancelled runs (if any) are just deleted.

Safe by default: runs in **dry-run** mode (prints the full plan, writes nothing).
Pass ``--commit`` to actually delete. The whole commit runs in one transaction —
any error rolls the entire thing back.

Run it INSIDE the backend container (it needs Django + the DB), e.g.:

    # dry-run preview (no writes):
    docker exec -i adminator-scratch-backend python - < scripts/delete_sales_production.py

    # actually delete + reverse:
    docker exec -i adminator-scratch-backend python - --commit < scripts/delete_sales_production.py

    # a different day:
    docker exec -i adminator-scratch-backend python - --date 2026-07-21 --commit \
        < scripts/delete_sales_production.py
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

from apps.inventory import services as inv_services  # noqa: E402
from apps.inventory.models import MovementReason  # noqa: E402
from apps.processed_materials import services as pm_services  # noqa: E402
from apps.processed_materials.models import (  # noqa: E402
    ProcessedMaterialMovementReason,
)
from apps.production.models import ProductionRun, ProductionStatus  # noqa: E402
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


def select(day: date, tz: ZoneInfo):
    start, end = local_day_bounds(day, tz)
    sales = (
        Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .prefetch_related("items__product")
        .order_by("occurred_at")
    )
    runs = (
        ProductionRun.objects.filter(scheduled_for=day)
        .select_related("product")
        .prefetch_related(
            "product__recipe_items__raw_material",
            "product__processed_usages__processed_material",
        )
        .order_by("created_at")
    )
    return sales, runs


# ── production reversal (mirror of execute_production, in reverse) ────────────
def reverse_production_run(run: ProductionRun, *, apply: bool, log) -> None:
    product = run.product
    qty = Decimal(run.quantity)
    ref = f"REVERSE-PROD-{run.id}"

    if run.status != ProductionStatus.COMPLETED:
        log(f"    · status={run.status} — no stock was moved; deleting row only")
        if apply:
            run.delete()
        return

    # 1) Return raw materials consumed by the recipe.
    for item in product.recipe_items.all():
        needed = Decimal(item.quantity) * qty
        log(f"    ↩ raw   +{needed}  {item.raw_material.name}")
        if apply:
            stock = inv_services.ensure_stock_item(raw_material=item.raw_material)
            inv_services.adjust_stock(
                stock_item=stock,
                quantity_delta=needed,
                reason=MovementReason.ADJUSTMENT_IN,
                reference=ref,
                note=f"Reversal of deleted production run {run.id}",
            )

    # 2) Return processed materials the product uses.
    for usage in product.processed_usages.all():
        needed = Decimal(usage.quantity) * qty
        log(f"    ↩ proc  +{needed}  {usage.processed_material.name}")
        if apply:
            stock = pm_services.ensure_stock(usage.processed_material)
            pm_services.adjust_stock(
                stock=stock,
                quantity_delta=needed,
                reason=ProcessedMaterialMovementReason.ADJUSTMENT_IN,
                reference=ref,
                note=f"Reversal of deleted production run {run.id}",
                allow_negative=True,
            )

    # 3) Remove the finished-product output that the run added.
    log(f"    ✂ out   -{qty}  {product.name} (finished stock)")
    if apply:
        prod_stock = inv_services.ensure_stock_item(product=product)
        inv_services.adjust_stock(
            stock_item=prod_stock,
            quantity_delta=-qty,
            reason=MovementReason.ADJUSTMENT_OUT,
            reference=ref,
            note=f"Reversal of deleted production run {run.id} output",
            allow_negative=True,
        )
        run.delete()


# ── main ─────────────────────────────────────────────────────────────────────
def run(day: date, tz: ZoneInfo, commit: bool) -> int:
    apply = commit
    mode = "COMMIT" if commit else "DRY-RUN (no writes)"
    print(f"Delete sales + production · {mode}")
    print(f"Business day : {day}  ({tz.key})")

    sales, runs = select(day, tz)
    sales = list(sales)
    runs = list(runs)

    n_items = sum(s.items.count() for s in sales)
    sales_total = sum((s.total for s in sales), Decimal("0"))
    completed = [r for r in runs if r.status == ProductionStatus.COMPLETED]
    print(
        f"Selected     : {len(sales)} sales ({n_items} line items, "
        f"total {sales_total}), {len(runs)} production runs "
        f"({len(completed)} completed / stock-reversed)\n"
    )

    if not sales and not runs:
        print("Nothing to delete for this day.")
        return 0

    try:
        with transaction.atomic():
            print("SALES")
            for s in sales:
                print(
                    f"  #{s.receipt_number}  {s.occurred_at:%Y-%m-%d %H:%M}Z  "
                    f"total {s.total}  ({s.items.count()} items) — delete + restore stock"
                )
                if apply:
                    sales_services.delete_sale(sale=s)

            print("\nPRODUCTION")
            for r in runs:
                print(
                    f"  {r.product.name} ×{r.quantity}  "
                    f"(run {str(r.id)[:8]}, {r.status}) — reverse + delete"
                )
                reverse_production_run(r, apply=apply, log=print)

            if not commit:
                raise DryRunRollback
    except DryRunRollback:
        print("\n" + "=" * 60)
        print("DRY-RUN — transaction rolled back, nothing written.")
        print("Re-run with --commit to actually delete + reverse.")
        return 0

    print("\n" + "=" * 60)
    print("DONE — committed.")
    print(f"  sales deleted            : {len(sales)}")
    print(f"  production runs deleted   : {len(runs)}")
    print(f"  runs stock-reversed       : {len(completed)}")
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
