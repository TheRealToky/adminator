"""Aggregations powering the dashboard."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, ExtractHour, TruncDate
from django.utils import timezone

from apps.catalog.models import Product
from apps.finance.models import Expense, Invoice, InvoiceStatus
from apps.inventory.models import ItemKind, StockItem
from apps.production.models import ProductionRun, ProductionStatus
from apps.sales.models import Sale, SaleItem


def _decimal_zero():
    return Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))


def _range_from(days: int) -> tuple[datetime, datetime]:
    end = timezone.now()
    start = end - timedelta(days=days)
    return start, end


def kpi_summary(days: int = 30) -> dict:
    """Headline KPIs for the dashboard top row."""
    start, end = _range_from(days)
    prev_start = start - timedelta(days=days)

    current_sales = Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end).aggregate(
        revenue=Coalesce(Sum("total"), _decimal_zero()),
        cogs=Coalesce(Sum("cost_of_goods"), _decimal_zero()),
        receipts=Count("id"),
    )
    previous_sales = Sale.objects.filter(occurred_at__gte=prev_start, occurred_at__lt=start).aggregate(
        revenue=Coalesce(Sum("total"), _decimal_zero()),
    )
    current_expenses = Expense.objects.filter(
        incurred_on__gte=start.date(), incurred_on__lt=end.date() + timedelta(days=1)
    ).aggregate(total=Coalesce(Sum("amount"), _decimal_zero()))

    revenue = Decimal(current_sales["revenue"])
    cogs = Decimal(current_sales["cogs"])
    expenses = Decimal(current_expenses["total"])
    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses

    prev_revenue = Decimal(previous_sales["revenue"])
    revenue_change_pct = (
        float(((revenue - prev_revenue) / prev_revenue) * 100) if prev_revenue else None
    )

    return {
        "window_days": days,
        "revenue": revenue,
        "cost_of_goods": cogs,
        "gross_profit": gross_profit,
        "operating_expenses": expenses,
        "net_profit": net_profit,
        "receipts": current_sales["receipts"],
        "average_ticket": (revenue / current_sales["receipts"]) if current_sales["receipts"] else Decimal("0"),
        "revenue_change_pct": revenue_change_pct,
    }


def sales_timeseries(days: int = 30) -> list[dict]:
    start, end = _range_from(days)
    rows = (
        Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .annotate(day=TruncDate("occurred_at"))
        .values("day")
        .annotate(
            revenue=Coalesce(Sum("total"), _decimal_zero()),
            cogs=Coalesce(Sum("cost_of_goods"), _decimal_zero()),
            receipts=Count("id"),
        )
        .order_by("day")
    )
    out = []
    for r in rows:
        revenue = Decimal(r["revenue"])
        cogs = Decimal(r["cogs"])
        out.append({
            "day": r["day"].isoformat(),
            "revenue": revenue,
            "cost_of_goods": cogs,
            "profit": revenue - cogs,
            "receipts": r["receipts"],
        })
    return out


def busy_hours(days: int = 30) -> list[dict]:
    """Aggregate receipts and revenue by hour-of-day."""
    start, end = _range_from(days)
    rows = (
        Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .annotate(hour=ExtractHour("occurred_at"))
        .values("hour")
        .annotate(
            revenue=Coalesce(Sum("total"), _decimal_zero()),
            receipts=Count("id"),
        )
        .order_by("hour")
    )
    by_hour = {r["hour"]: r for r in rows}
    return [
        {
            "hour": h,
            "label": f"{h:02d}:00",
            "revenue": Decimal(by_hour.get(h, {}).get("revenue", 0)),
            "receipts": int(by_hour.get(h, {}).get("receipts", 0)),
        }
        for h in range(24)
    ]


def top_products(days: int = 30, limit: int = 10) -> list[dict]:
    start, end = _range_from(days)
    qs = (
        SaleItem.objects.filter(sale__occurred_at__gte=start, sale__occurred_at__lt=end)
        .values("product_id", "product__name", "product__sku")
        .annotate(
            quantity=Coalesce(Sum("quantity"), _decimal_zero()),
            revenue=Coalesce(Sum("line_total"), _decimal_zero()),
        )
        .order_by("-revenue")[:limit]
    )
    return [
        {
            "product_id": str(r["product_id"]),
            "name": r["product__name"],
            "sku": r["product__sku"],
            "quantity": Decimal(r["quantity"]),
            "revenue": Decimal(r["revenue"]),
        }
        for r in qs
    ]


def payment_mix(days: int = 30) -> list[dict]:
    start, end = _range_from(days)
    rows = (
        Sale.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
        .values("payment_method")
        .annotate(
            revenue=Coalesce(Sum("total"), _decimal_zero()),
            receipts=Count("id"),
        )
        .order_by("-revenue")
    )
    return [
        {
            "method": r["payment_method"],
            "revenue": Decimal(r["revenue"]),
            "receipts": r["receipts"],
        }
        for r in rows
    ]


def stock_health() -> dict:
    """Counts of healthy vs low stock items, plus the lowest items."""
    product_low = Q(kind=ItemKind.PRODUCT, quantity__lte=F("product__reorder_threshold"))
    material_low = Q(
        kind=ItemKind.RAW_MATERIAL, quantity__lte=F("raw_material__reorder_threshold")
    )
    qs = StockItem.objects.select_related("product", "raw_material")
    low = qs.filter(product_low | material_low)
    total = qs.count()

    lowest = list(low.order_by("quantity")[:10])
    lowest_payload = []
    for item in lowest:
        target = item.product or item.raw_material
        lowest_payload.append({
            "id": str(item.id),
            "kind": item.kind,
            "name": target.name if target else "(unknown)",
            "sku": target.sku if target else "",
            "unit": target.unit if target else "",
            "quantity": Decimal(item.quantity),
            "reorder_threshold": Decimal(
                target.reorder_threshold if target else 0
            ),
        })

    return {
        "total_items": total,
        "low_stock_count": low.count(),
        "lowest_items": lowest_payload,
    }


def inventory_on_hand_value() -> dict:
    """Carrying value of unsold inventory at current per-unit costs.

    Finished goods are valued at `Product.production_cost`; raw materials at
    `RawMaterial.unit_cost`. Both are *latest* values — if input prices have
    moved since stock was acquired, the figure drifts accordingly.
    """
    money = DecimalField(max_digits=18, decimal_places=4)

    product_agg = StockItem.objects.filter(
        kind=ItemKind.PRODUCT, product__isnull=False
    ).aggregate(
        units=Coalesce(Sum("quantity"), _decimal_zero()),
        value=Coalesce(
            Sum(F("quantity") * F("product__production_cost"), output_field=money),
            _decimal_zero(),
        ),
    )
    raw_agg = StockItem.objects.filter(
        kind=ItemKind.RAW_MATERIAL, raw_material__isnull=False
    ).aggregate(
        value=Coalesce(
            Sum(F("quantity") * F("raw_material__unit_cost"), output_field=money),
            _decimal_zero(),
        ),
    )

    finished_value = Decimal(product_agg["value"]).quantize(Decimal("0.01"))
    raw_value = Decimal(raw_agg["value"]).quantize(Decimal("0.01"))

    return {
        "finished_goods_value": finished_value,
        "finished_goods_units": Decimal(product_agg["units"]),
        "raw_materials_value": raw_value,
        "total_value": (finished_value + raw_value).quantize(Decimal("0.01")),
    }


def production_summary(days: int = 30) -> dict:
    start, end = _range_from(days)
    qs = ProductionRun.objects.filter(
        scheduled_for__gte=start.date(), scheduled_for__lt=end.date() + timedelta(days=1)
    )
    completed = qs.filter(status=ProductionStatus.COMPLETED)
    by_day = (
        completed
        .values(day=F("scheduled_for"))
        .annotate(
            units=Coalesce(Sum("quantity"), _decimal_zero()),
            cost=Coalesce(Sum("cost"), _decimal_zero()),
            runs=Count("id"),
        )
        .order_by("day")
    )
    return {
        "total_runs": qs.count(),
        "completed_runs": completed.count(),
        "units_produced": Decimal(
            completed.aggregate(v=Coalesce(Sum("quantity"), _decimal_zero()))["v"]
        ),
        "total_cost": Decimal(
            completed.aggregate(v=Coalesce(Sum("cost"), _decimal_zero()))["v"]
        ),
        "by_day": [
            {
                "day": r["day"].isoformat(),
                "units": Decimal(r["units"]),
                "cost": Decimal(r["cost"]),
                "runs": r["runs"],
            }
            for r in by_day
        ],
    }


def expense_breakdown(days: int = 30) -> list[dict]:
    start, end = _range_from(days)
    rows = (
        Expense.objects.filter(
            incurred_on__gte=start.date(), incurred_on__lt=end.date() + timedelta(days=1)
        )
        .values("category_id", "category__name")
        .annotate(total=Coalesce(Sum("amount"), _decimal_zero()))
        .order_by("-total")
    )
    return [
        {
            "category_id": str(r["category_id"]),
            "name": r["category__name"],
            "total": Decimal(r["total"]),
        }
        for r in rows
    ]


def invoices_status_breakdown() -> dict:
    rows = (
        Invoice.objects.values("status")
        .annotate(
            count=Count("id"),
            total=Coalesce(Sum("amount"), _decimal_zero()),
        )
    )
    return {
        "by_status": [
            {
                "status": r["status"],
                "count": r["count"],
                "total": Decimal(r["total"]),
            }
            for r in rows
        ],
        "overdue_total": Decimal(
            Invoice.objects.filter(
                due_date__lt=date.today()
            ).exclude(
                status__in=[InvoiceStatus.PAID, InvoiceStatus.CANCELLED]
            ).aggregate(v=Coalesce(Sum(F("amount") - F("amount_paid")), _decimal_zero()))["v"]
        ),
    }


def naive_sales_forecast(history_days: int = 60, forecast_days: int = 14) -> list[dict]:
    """7-day-of-week moving average forecast.

    Deliberately simple — keeps the backend free of heavy ML deps. For better
    accuracy, the included Jupyter notebooks demonstrate Prophet / SARIMAX.
    """
    today = timezone.localdate()
    start = today - timedelta(days=history_days)

    rows = (
        Sale.objects.filter(occurred_at__date__gte=start)
        .annotate(day=TruncDate("occurred_at"))
        .values("day")
        .annotate(revenue=Coalesce(Sum("total"), _decimal_zero()))
        .order_by("day")
    )
    by_weekday: dict[int, list[Decimal]] = {i: [] for i in range(7)}
    for r in rows:
        by_weekday[r["day"].weekday()].append(Decimal(r["revenue"]))

    avg_by_weekday = {
        w: (sum(v) / len(v) if v else Decimal("0"))
        for w, v in by_weekday.items()
    }

    forecast = []
    for offset in range(1, forecast_days + 1):
        day = today + timedelta(days=offset)
        forecast.append({
            "day": day.isoformat(),
            "forecast_revenue": avg_by_weekday[day.weekday()].quantize(Decimal("0.01")),
            "method": "weekday_moving_average",
        })
    return forecast
