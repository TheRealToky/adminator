"""
Monthly Sales Recap Helper for Adminator Notebooks.

Allows analyzing, summarizing, and visualizing sales performance for any specified
calendar month using data loaded from db.py.
"""
from __future__ import annotations

import calendar
import datetime
from typing import Optional, Union, Tuple, Dict, Any
import pandas as pd
import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    from IPython.display import display, HTML
    IN_IPYTHON = True
except ImportError:
    IN_IPYTHON = False

# Opt in to modern pandas behavior to eliminate downcasting warnings in pandas >= 2.1
try:
    pd.set_option("future.no_silent_downcasting", True)
except Exception:
    pass

from db import load_sales, load_sale_items


# User-friendly label maps matching backend PaymentMethod
PAYMENT_LABELS = {
    "cash": "Cash",
    "mobile_money": "Mobile Money",
    "card": "Card",
    "bank_transfer": "Bank Transfer",
    "credit": "Credit / Account",
}

WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


def parse_month_boundaries(
    target: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    sales_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp, str, str, str]:
    """
    Determine the start and end timestamps for the target month and the previous month.

    Args:
        target: Can be:
            - None: selects the month of the latest sale in sales_df (or current month).
            - '2026-05': Year-Month string format.
            - '2026-05-18' / date / Timestamp: extracts year and month.
        sales_df: Optional sales DataFrame to infer the latest date if target is None.

    Returns:
        (month_start, month_end, prev_month_start, prev_month_end, month_label, month_slug, month_title)
    """
    if target is None:
        if sales_df is not None and not sales_df.empty and "occurred_at" in sales_df:
            ref_dt = sales_df["occurred_at"].max()
            if hasattr(ref_dt, "tz") and ref_dt.tz is not None:
                ref_dt = ref_dt.tz_localize(None)
        else:
            ref_dt = pd.Timestamp.now()
        year, month = ref_dt.year, ref_dt.month
    elif isinstance(target, str) and len(target.strip()) == 7 and target[4] == "-":
        parts = target.strip().split("-")
        year, month = int(parts[0]), int(parts[1])
    else:
        dt = pd.to_datetime(target)
        if hasattr(dt, "tz") and dt.tz is not None:
            dt = dt.tz_localize(None)
        year, month = dt.year, dt.month

    # Current month boundaries
    _, last_day = calendar.monthrange(year, month)
    month_start = pd.Timestamp(year, month, 1, 0, 0, 0)
    month_end = pd.Timestamp(year, month, last_day, 23, 59, 59, 999999)

    # Previous month boundaries for Month-over-Month (MoM) comparison
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    _, prev_last_day = calendar.monthrange(prev_year, prev_month)
    prev_month_start = pd.Timestamp(prev_year, prev_month, 1, 0, 0, 0)
    prev_month_end = pd.Timestamp(prev_year, prev_month, prev_last_day, 23, 59, 59, 999999)

    month_name = calendar.month_name[month]
    month_title = f"{month_name} {year}"
    month_label = f"{month_name} {year} ({month_start:%b 01} – {month_end:%b %d, %Y})"
    month_slug = f"{year}_{month:02d}"

    return month_start, month_end, prev_month_start, prev_month_end, month_label, month_slug, month_title


def get_monthly_sales_summary(
    target_month: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    sales: Optional[pd.DataFrame] = None,
    items: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Compute comprehensive monthly sales analytics, trends, and breakdowns.

    Returns a dictionary containing:
        - kpis: summary totals, daily averages, and Month-over-Month (MoM) changes
        - daily: daily breakdown DataFrame for all days of the month (1..31)
        - weekdays: performance aggregated by day of week (Monday to Sunday)
        - categories: product category breakdown DataFrame
        - payments: payment method breakdown DataFrame
        - hourly: hourly distribution DataFrame
        - top_products: top-selling products DataFrame
        - metadata: month boundaries, labels, and database active ranges
    """
    if sales is None:
        sales = load_sales()
    if items is None:
        items = load_sale_items()

    sales = sales.copy()
    items = items.copy()

    # Convert database Decimal/numeric columns to float64 early to prevent downcasting issues
    for col in ["subtotal", "discount", "total", "cost_of_goods", "profit"]:
        if col in sales.columns:
            sales[col] = pd.to_numeric(sales[col], errors="coerce").fillna(0.0)

    for col in ["quantity", "unit_price", "unit_cost", "line_total"]:
        if col in items.columns:
            items[col] = pd.to_numeric(items[col], errors="coerce").fillna(0.0)

    db_min = sales["occurred_at"].min() if not sales.empty else None
    db_max = sales["occurred_at"].max() if not sales.empty else None

    (
        m_start_naive,
        m_end_naive,
        prev_m_start_naive,
        prev_m_end_naive,
        month_label,
        month_slug,
        month_title,
    ) = parse_month_boundaries(target_month, sales)

    # Timezone-aware alignment
    tz = sales["occurred_at"].dt.tz
    if tz is not None:
        m_start = m_start_naive.tz_localize(tz) if m_start_naive.tz is None else m_start_naive.tz_convert(tz)
        m_end = m_end_naive.tz_localize(tz) if m_end_naive.tz is None else m_end_naive.tz_convert(tz)
        prev_m_start = prev_m_start_naive.tz_localize(tz) if prev_m_start_naive.tz is None else prev_m_start_naive.tz_convert(tz)
        prev_m_end = prev_m_end_naive.tz_localize(tz) if prev_m_end_naive.tz is None else prev_m_end_naive.tz_convert(tz)
    else:
        m_start = m_start_naive.tz_localize(None) if m_start_naive.tz is not None else m_start_naive
        m_end = m_end_naive.tz_localize(None) if m_end_naive.tz is not None else m_end_naive
        prev_m_start = prev_m_start_naive.tz_localize(None) if prev_m_start_naive.tz is not None else prev_m_start_naive
        prev_m_end = prev_m_end_naive.tz_localize(None) if prev_m_end_naive.tz is not None else prev_m_end_naive

    # Current month data slices
    cur_sales = sales[(sales["occurred_at"] >= m_start) & (sales["occurred_at"] <= m_end)].copy()
    cur_items = items[(items["occurred_at"] >= m_start) & (items["occurred_at"] <= m_end)].copy()

    # Previous month data slices for MoM comparison
    prev_sales = sales[(sales["occurred_at"] >= prev_m_start) & (sales["occurred_at"] <= prev_m_end)].copy()
    prev_items = items[(items["occurred_at"] >= prev_m_start) & (items["occurred_at"] <= prev_m_end)].copy()

    # KPIs Calculation
    cur_revenue = float(cur_sales["total"].sum()) if not cur_sales.empty else 0.0
    cur_cogs = float(cur_sales["cost_of_goods"].sum()) if not cur_sales.empty else 0.0
    cur_profit = float(cur_sales["profit"].sum()) if not cur_sales.empty else 0.0
    cur_receipts = int(len(cur_sales))
    cur_units = float(cur_items["quantity"].sum()) if not cur_items.empty else 0.0
    cur_discount = float(cur_sales["discount"].sum()) if not cur_sales.empty else 0.0
    cur_aov = (cur_revenue / cur_receipts) if cur_receipts > 0 else 0.0
    cur_margin = (cur_profit / cur_revenue * 100.0) if cur_revenue > 0 else 0.0

    days_in_month = (m_end_naive.date() - m_start_naive.date()).days + 1
    daily_avg_revenue = cur_revenue / days_in_month if days_in_month > 0 else 0.0
    daily_avg_receipts = cur_receipts / days_in_month if days_in_month > 0 else 0.0

    prev_revenue = float(prev_sales["total"].sum()) if not prev_sales.empty else 0.0
    prev_cogs = float(prev_sales["cost_of_goods"].sum()) if not prev_sales.empty else 0.0
    prev_profit = float(prev_sales["profit"].sum()) if not prev_sales.empty else 0.0
    prev_receipts = int(len(prev_sales))
    prev_units = float(prev_items["quantity"].sum()) if not prev_items.empty else 0.0
    prev_aov = (prev_revenue / prev_receipts) if prev_receipts > 0 else 0.0

    def calc_mom(cur: float, prev: float) -> Optional[float]:
        if prev > 0:
            return ((cur - prev) / prev) * 100.0
        return None

    kpis = {
        "revenue": cur_revenue,
        "cogs": cur_cogs,
        "gross_profit": cur_profit,
        "gross_margin_pct": cur_margin,
        "receipts": cur_receipts,
        "units_sold": cur_units,
        "discounts": cur_discount,
        "aov": cur_aov,
        "days_in_month": days_in_month,
        "daily_avg_revenue": daily_avg_revenue,
        "daily_avg_receipts": daily_avg_receipts,
        "mom_revenue_pct": calc_mom(cur_revenue, prev_revenue),
        "mom_profit_pct": calc_mom(cur_profit, prev_profit),
        "mom_receipts_pct": calc_mom(cur_receipts, prev_receipts),
        "mom_aov_pct": calc_mom(cur_aov, prev_aov),
        "prev_revenue": prev_revenue,
        "prev_profit": prev_profit,
        "prev_receipts": prev_receipts,
    }

    # 1. Full Daily Breakdown (1st through last day of month)
    cur_sales["date"] = cur_sales["occurred_at"].dt.date
    cur_items["date"] = cur_items["occurred_at"].dt.date

    month_dates = [m_start_naive.date() + datetime.timedelta(days=i) for i in range(days_in_month)]
    daily_base = pd.DataFrame({
        "date": month_dates,
        "day_num": [d.day for d in month_dates],
        "day": [d.strftime("%A") for d in month_dates],
    })

    if not cur_sales.empty:
        sales_agg = (
            cur_sales.groupby("date")
            .agg(
                revenue=("total", "sum"),
                cogs=("cost_of_goods", "sum"),
                profit=("profit", "sum"),
                receipts=("id", "count"),
            )
            .reset_index()
        )
    else:
        sales_agg = pd.DataFrame({
            "date": pd.Series(dtype="object"),
            "revenue": pd.Series(dtype="float64"),
            "cogs": pd.Series(dtype="float64"),
            "profit": pd.Series(dtype="float64"),
            "receipts": pd.Series(dtype="int64"),
        })

    if not cur_items.empty:
        items_agg = (
            cur_items.groupby("date")
            .agg(units_sold=("quantity", "sum"))
            .reset_index()
        )
    else:
        items_agg = pd.DataFrame({
            "date": pd.Series(dtype="object"),
            "units_sold": pd.Series(dtype="float64"),
        })

    daily = daily_base.merge(sales_agg, on="date", how="left").merge(items_agg, on="date", how="left")
    daily["revenue"] = pd.to_numeric(daily["revenue"], errors="coerce").fillna(0.0)
    daily["cogs"] = pd.to_numeric(daily["cogs"], errors="coerce").fillna(0.0)
    daily["profit"] = pd.to_numeric(daily["profit"], errors="coerce").fillna(0.0)
    daily["receipts"] = pd.to_numeric(daily["receipts"], errors="coerce").fillna(0).astype(int)
    daily["units_sold"] = pd.to_numeric(daily["units_sold"], errors="coerce").fillna(0.0)
    daily["aov"] = np.where(daily["receipts"] > 0, daily["revenue"] / daily["receipts"], 0.0)
    daily["margin_pct"] = np.where(daily["revenue"] > 0, (daily["profit"] / daily["revenue"]) * 100.0, 0.0)
    daily["rolling7_revenue"] = daily["revenue"].rolling(7, min_periods=1).mean()

    # 2. Weekday Performance Aggregation (Monday..Sunday seasonality)
    weekdays = (
        daily.groupby("day")
        .agg(
            days_count=("date", "count"),
            total_revenue=("revenue", "sum"),
            avg_revenue=("revenue", "mean"),
            total_receipts=("receipts", "sum"),
            avg_receipts=("receipts", "mean"),
            total_profit=("profit", "sum"),
        )
        .reindex(WEEKDAY_ORDER)
        .reset_index()
    )
    weekdays["avg_aov"] = np.where(weekdays["total_receipts"] > 0, weekdays["total_revenue"] / weekdays["total_receipts"], 0.0)
    weekdays["revenue_share_pct"] = (weekdays["total_revenue"] / cur_revenue * 100.0) if cur_revenue > 0 else 0.0

    # 3. Product Category Breakdown
    if not cur_items.empty:
        cur_items["est_cost"] = cur_items["quantity"] * cur_items["unit_cost"]
        cur_items["est_profit"] = cur_items["line_total"] - cur_items["est_cost"]
        categories = (
            cur_items.groupby("category")
            .agg(
                units_sold=("quantity", "sum"),
                revenue=("line_total", "sum"),
                profit=("est_profit", "sum"),
            )
            .reset_index()
        )
        categories["revenue_share_pct"] = (categories["revenue"] / cur_revenue * 100.0) if cur_revenue > 0 else 0.0
        categories["margin_pct"] = np.where(categories["revenue"] > 0, (categories["profit"] / categories["revenue"]) * 100.0, 0.0)
        categories = categories.sort_values(by="revenue", ascending=False).reset_index(drop=True)
    else:
        categories = pd.DataFrame(columns=["category", "units_sold", "revenue", "profit", "margin_pct", "revenue_share_pct"])

    # 4. Payment Method Breakdown
    if not cur_sales.empty:
        payments = (
            cur_sales.groupby("payment_method")
            .agg(
                receipts=("id", "count"),
                revenue=("total", "sum"),
            )
            .reset_index()
        )
        payments["payment_label"] = payments["payment_method"].map(lambda p: PAYMENT_LABELS.get(p, p.replace("_", " ").capitalize()))
        payments["revenue_share_pct"] = (payments["revenue"] / cur_revenue * 100.0) if cur_revenue > 0 else 0.0
        payments = payments.sort_values(by="revenue", ascending=False).reset_index(drop=True)
    else:
        payments = pd.DataFrame(columns=["payment_method", "payment_label", "receipts", "revenue", "revenue_share_pct"])

    # 5. Hourly Distribution
    if not cur_sales.empty:
        hourly = (
            cur_sales.assign(hour=cur_sales["occurred_at"].dt.hour)
            .groupby("hour")
            .agg(
                receipts=("id", "count"),
                revenue=("total", "sum"),
            )
            .reset_index()
        )
        hourly["revenue_share_pct"] = (hourly["revenue"] / cur_revenue * 100.0) if cur_revenue > 0 else 0.0
        hourly = hourly.sort_values(by="hour").reset_index(drop=True)
    else:
        hourly = pd.DataFrame(columns=["hour", "receipts", "revenue", "revenue_share_pct"])

    # 6. Top Selling Products
    if not cur_items.empty:
        top_products = (
            cur_items.groupby(["product_id", "product_name", "category"])
            .agg(
                units_sold=("quantity", "sum"),
                revenue=("line_total", "sum"),
                avg_unit_price=("unit_price", "mean"),
                avg_unit_cost=("unit_cost", "mean"),
            )
            .reset_index()
        )
        top_products["estimated_cost"] = top_products["units_sold"] * top_products["avg_unit_cost"]
        top_products["estimated_profit"] = top_products["revenue"] - top_products["estimated_cost"]
        top_products["margin_pct"] = np.where(
            top_products["revenue"] > 0,
            (top_products["estimated_profit"] / top_products["revenue"]) * 100.0,
            0.0,
        )
        top_products["revenue_share_pct"] = (top_products["revenue"] / cur_revenue * 100.0) if cur_revenue > 0 else 0.0
        top_products = top_products.sort_values(by="revenue", ascending=False).reset_index(drop=True)
    else:
        top_products = pd.DataFrame(columns=["product_id", "product_name", "category", "units_sold", "revenue", "estimated_profit", "margin_pct", "revenue_share_pct"])

    return {
        "kpis": kpis,
        "daily": daily,
        "weekdays": weekdays,
        "categories": categories,
        "payments": payments,
        "hourly": hourly,
        "top_products": top_products,
        "metadata": {
            "month_label": month_label,
            "month_title": month_title,
            "month_slug": month_slug,
            "start_date": m_start_naive,
            "end_date": m_end_naive,
            "days_in_month": days_in_month,
            "cur_sales_count": len(cur_sales),
            "cur_items_count": len(cur_items),
            "db_min_date": db_min,
            "db_max_date": db_max,
        },
    }


def create_monthly_sales_figures(summary: Dict[str, Any]):
    """Generate interactive Plotly dashboard charts for the monthly recap."""
    if not HAS_PLOTLY:
        return None

    daily = summary["daily"]
    categories = summary["categories"]
    payments = summary["payments"]
    weekdays = summary["weekdays"]
    top_products = summary["top_products"].head(10)
    meta = summary["metadata"]

    # Figure 1: Daily Revenue & Gross Profit with 7-Day Moving Average
    fig_daily = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Revenue, Profit & 7-day Avg ({meta['month_title']})",
            "Daily Order Volume & Average Order Value (AOV)"
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": True}]],
    )

    # Col 1: Daily Revenue bars + 7-Day Trendline + Profit bars
    fig_daily.add_trace(
        go.Bar(
            x=daily["date"],
            y=daily["revenue"],
            name="Daily Revenue",
            marker_color="#2563eb",
            opacity=0.75,
        ),
        row=1, col=1,
    )
    fig_daily.add_trace(
        go.Bar(
            x=daily["date"],
            y=daily["profit"],
            name="Gross Profit",
            marker_color="#10b981",
            opacity=0.8,
        ),
        row=1, col=1,
    )
    fig_daily.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["rolling7_revenue"],
            name="7-Day Moving Avg",
            mode="lines",
            line=dict(color="#f97316", width=3),
        ),
        row=1, col=1,
    )

    # Col 2: Receipts bars + AOV line
    fig_daily.add_trace(
        go.Bar(
            x=daily["date"],
            y=daily["receipts"],
            name="Receipts / Orders",
            marker_color="#8b5cf6",
            opacity=0.75,
        ),
        row=1, col=2, secondary_y=False,
    )
    fig_daily.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["aov"],
            name="AOV",
            mode="lines+markers",
            marker=dict(size=6, color="#f59e0b"),
            line=dict(width=2.5, color="#f59e0b"),
        ),
        row=1, col=2, secondary_y=True,
    )

    fig_daily.update_layout(
        barmode="group",
        height=450,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        template="plotly_white",
    )
    fig_daily.update_yaxes(title_text="Amount", row=1, col=1)
    fig_daily.update_yaxes(title_text="Orders count", row=1, col=2, secondary_y=False)
    fig_daily.update_yaxes(title_text="AOV", row=1, col=2, secondary_y=True)

    # Figure 2: Category & Payment Breakdown (with separate top-right legends!)
    fig_mix = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=("Revenue by Product Category", "Revenue by Payment Method"),
        horizontal_spacing=0.18,
    )

    if not categories.empty:
        fig_mix.add_trace(
            go.Pie(
                labels=categories["category"],
                values=categories["revenue"],
                hole=0.45,
                name="Category",
                legend="legend",
                textinfo="percent",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>Revenue: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
                marker_colors=["#f97316", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"],
            ),
            row=1, col=1,
        )

    if not payments.empty:
        fig_mix.add_trace(
            go.Pie(
                labels=payments["payment_label"],
                values=payments["revenue"],
                hole=0.45,
                name="Payment",
                legend="legend2",
                textinfo="percent",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>Revenue: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
                marker_colors=["#06b6d4", "#10b981", "#f97316", "#6366f1", "#a855f7"],
            ),
            row=1, col=2,
        )

    # Offset donut centers leftwards so top-right legends never collide
    if len(fig_mix.data) >= 1:
        fig_mix.data[0].domain = dict(x=[0.0, 0.33], y=[0.0, 1.0])
    if len(fig_mix.data) >= 2:
        fig_mix.data[1].domain = dict(x=[0.52, 0.85], y=[0.0, 1.0])

    fig_mix.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(
            title_text="<b>Categories</b>",
            x=0.48,
            y=1.0,
            xanchor="right",
            yanchor="top",
            orientation="v",
            font=dict(size=11),
        ),
        legend2=dict(
            title_text="<b>Payment Methods</b>",
            x=1.0,
            y=1.0,
            xanchor="right",
            yanchor="top",
            orientation="v",
            font=dict(size=11),
        ),
        template="plotly_white",
    )

    # Figure 3: Top 10 Best Selling Products
    if not top_products.empty:
        top_sorted = top_products.sort_values(by="revenue", ascending=True)
        fig_products = go.Figure(
            go.Bar(
                x=top_sorted["revenue"],
                y=top_sorted["product_name"],
                orientation="h",
                marker_color="#3b82f6",
                text=top_sorted.apply(
                    lambda r: f"{r['revenue']:,.0f} ({r['units_sold']:,.0f} sold, {r['margin_pct']:.1f}% margin)",
                    axis=1,
                ),
                textposition="auto",
            )
        )
        fig_products.update_layout(
            title=f"Top 10 Products by Revenue ({meta['month_title']})",
            xaxis_title="Revenue",
            yaxis_title="",
            height=420,
            margin=dict(l=150, r=40, t=60, b=40),
            template="plotly_white",
        )
    else:
        fig_products = None

    # Figure 4: Day-of-Week Seasonality Performance
    fig_weekdays = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Average Revenue by Day of Week", "Total Receipts by Day of Week"),
    )
    fig_weekdays.add_trace(
        go.Bar(
            x=weekdays["day"],
            y=weekdays["avg_revenue"],
            name="Avg Daily Revenue",
            marker_color="#3b82f6",
            text=weekdays["avg_revenue"].map(lambda v: f"{v:,.0f}"),
            textposition="auto",
        ),
        row=1, col=1,
    )
    fig_weekdays.add_trace(
        go.Bar(
            x=weekdays["day"],
            y=weekdays["total_receipts"],
            name="Total Orders",
            marker_color="#10b981",
            text=weekdays["total_receipts"].map(lambda v: f"{v:,d}"),
            textposition="auto",
        ),
        row=1, col=2,
    )
    fig_weekdays.update_layout(
        height=380,
        margin=dict(l=40, r=40, t=60, b=40),
        template="plotly_white",
        showlegend=False,
    )

    return fig_daily, fig_mix, fig_products, fig_weekdays


def _export_charts_matplotlib(
    summary: Dict[str, Any], output_dir: str, format: str, month_slug: str
) -> Dict[str, str]:
    """Fallback high-resolution exporter using Matplotlib."""
    import os
    import matplotlib.pyplot as plt

    saved_files = {}
    daily = summary["daily"]
    categories = summary["categories"]
    payments = summary["payments"]
    weekdays = summary["weekdays"]
    top_products = summary["top_products"].head(10)
    meta = summary["metadata"]

    # 1. Daily Sales Trend
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
    ax1.bar(daily["day_num"], daily["revenue"], label="Revenue", color="#2563eb", alpha=0.7)
    ax1.plot(daily["day_num"], daily["rolling7_revenue"], label="7-Day Avg", color="#f97316", linewidth=2.5)
    ax1.set_title(f"Revenue, Profit & 7-day Avg ({meta['month_title']})", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Day of Month")
    ax1.set_ylabel("Amount")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2_twin = ax2.twinx()
    ax2.bar(daily["day_num"], daily["receipts"], color="#8b5cf6", alpha=0.7, label="Receipts")
    ax2_twin.plot(daily["day_num"], daily["aov"], color="#f59e0b", marker="o", markersize=4, linewidth=2, label="AOV")
    ax2.set_title("Daily Orders & Average Order Value (AOV)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Day of Month")
    ax2.set_ylabel("Orders")
    ax2_twin.set_ylabel("AOV")
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    p1 = os.path.join(output_dir, f"01_monthly_daily_sales_{month_slug}.{format}")
    fig.savefig(p1, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["daily_sales"] = p1

    # 2. Category & Payment Mix
    fig, (ax_c, ax_p) = plt.subplots(1, 2, figsize=(14, 5))
    if not categories.empty:
        wedges_c, _, _ = ax_c.pie(
            categories["revenue"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#f97316", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"],
            textprops=dict(color="white", weight="bold", size=9),
        )
        ax_c.legend(
            wedges_c,
            categories["category"],
            title="Categories",
            loc="upper right",
            bbox_to_anchor=(1.25, 1.0),
            fontsize=9,
        )
        ax_c.set_title("Revenue by Product Category", fontsize=12, fontweight="bold")

    if not payments.empty:
        wedges_p, _, _ = ax_p.pie(
            payments["revenue"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#06b6d4", "#10b981", "#f97316", "#6366f1", "#a855f7"],
            textprops=dict(color="white", weight="bold", size=9),
        )
        ax_p.legend(
            wedges_p,
            payments["payment_label"],
            title="Payment Methods",
            loc="upper right",
            bbox_to_anchor=(1.28, 1.0),
            fontsize=9,
        )
        ax_p.set_title("Revenue by Payment Method", fontsize=12, fontweight="bold")

    plt.tight_layout()
    p2 = os.path.join(output_dir, f"02_monthly_category_payment_mix_{month_slug}.{format}")
    fig.savefig(p2, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["category_payment_mix"] = p2

    # 3. Top Products
    if not top_products.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        sorted_prod = top_products.sort_values(by="revenue", ascending=True)
        ax.barh(sorted_prod["product_name"], sorted_prod["revenue"], color="#3b82f6")
        ax.set_title(f"Top 10 Products by Revenue ({meta['month_title']})", fontsize=12, fontweight="bold")
        ax.set_xlabel("Revenue")
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        p3 = os.path.join(output_dir, f"03_monthly_top_products_{month_slug}.{format}")
        fig.savefig(p3, dpi=200, bbox_inches="tight")
        plt.close(fig)
        saved_files["top_products"] = p3

    # 4. Weekday Seasonality
    fig, (ax_w1, ax_w2) = plt.subplots(1, 2, figsize=(14, 5))
    ax_w1.bar(weekdays["day"], weekdays["avg_revenue"], color="#3b82f6")
    ax_w1.set_title("Average Daily Revenue by Day of Week", fontsize=12, fontweight="bold")
    ax_w1.set_xticklabels(weekdays["day"], rotation=25)
    ax_w1.grid(True, linestyle="--", alpha=0.5)

    ax_w2.bar(weekdays["day"], weekdays["total_receipts"], color="#10b981")
    ax_w2.set_title("Total Orders by Day of Week", fontsize=12, fontweight="bold")
    ax_w2.set_xticklabels(weekdays["day"], rotation=25)
    ax_w2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    p4 = os.path.join(output_dir, f"04_monthly_weekday_performance_{month_slug}.{format}")
    fig.savefig(p4, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["weekday_performance"] = p4

    return saved_files


def export_monthly_sales_charts(
    summary: Dict[str, Any],
    output_dir: str = "exports",
    format: str = "png",
    scale: int = 2,
) -> Dict[str, str]:
    """
    Export all monthly sales charts to static image files (PNG, JPEG, PDF, SVG).

    Args:
        summary: Dictionary returned by get_monthly_sales_summary / recap_sales_for_month.
        output_dir: Directory where images will be saved.
        format: Image format ('png', 'jpeg', 'pdf', 'svg').
        scale: Resolution scale factor for Plotly output (default: 2 for high-DPI).

    Returns:
        Dictionary mapping chart names to their saved file paths.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    meta = summary["metadata"]
    month_slug = meta["month_slug"]
    saved_files = {}

    figs = create_monthly_sales_figures(summary)
    exported_via_plotly = False

    if figs and HAS_PLOTLY:
        fig_daily, fig_mix, fig_products, fig_weekdays = figs
        try:
            p1 = os.path.join(output_dir, f"01_monthly_daily_sales_{month_slug}.{format}")
            fig_daily.write_image(p1, format=format, scale=scale, width=1200, height=500)
            saved_files["daily_sales"] = p1

            p2 = os.path.join(output_dir, f"02_monthly_category_payment_mix_{month_slug}.{format}")
            fig_mix.write_image(p2, format=format, scale=scale, width=1000, height=450)
            saved_files["category_payment_mix"] = p2

            if fig_products:
                p3 = os.path.join(output_dir, f"03_monthly_top_products_{month_slug}.{format}")
                fig_products.write_image(p3, format=format, scale=scale, width=1000, height=500)
                saved_files["top_products"] = p3

            p4 = os.path.join(output_dir, f"04_monthly_weekday_performance_{month_slug}.{format}")
            fig_weekdays.write_image(p4, format=format, scale=scale, width=1100, height=450)
            saved_files["weekday_performance"] = p4

            exported_via_plotly = True
        except Exception:
            exported_via_plotly = False

    if not exported_via_plotly:
        saved_files = _export_charts_matplotlib(summary, output_dir=output_dir, format=format, month_slug=month_slug)

    return saved_files


def print_monthly_recap_terminal(summary: Dict[str, Any]):
    """Pretty-print monthly sales recap for terminal or plain console environments."""
    k = summary["kpis"]
    meta = summary["metadata"]
    print("=" * 72)
    print(f"  MONTHLY SALES RECAP: {meta['month_label']}")
    print("=" * 72)

    def mom_str(pct):
        if pct is None:
            return "N/A (no prior month)"
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}% MoM"

    print(f" Gross Revenue:      {k['revenue']:>15,.2f}  ({mom_str(k['mom_revenue_pct'])})")
    print(f" Cost of Goods:      {k['cogs']:>15,.2f}")
    print(f" Gross Profit:       {k['gross_profit']:>15,.2f}  ({mom_str(k['mom_profit_pct'])})")
    print(f" Gross Margin:       {k['gross_margin_pct']:>14.1f}%")
    print(f" Total Receipts:     {k['receipts']:>15,d}  ({mom_str(k['mom_receipts_pct'])})")
    print(f" Average Order (AOV):{k['aov']:>15,.2f}  ({mom_str(k['mom_aov_pct'])})")
    print(f" Total Units Sold:   {k['units_sold']:>15,.1f}")
    print(f" Daily Avg Revenue:  {k['daily_avg_revenue']:>15,.2f}")
    print(f" Daily Avg Receipts: {k['daily_avg_receipts']:>15,.1f}")
    print("-" * 72)

    print("\n[Sales by Product Category]")
    if not summary["categories"].empty:
        c_df = summary["categories"][["category", "units_sold", "revenue", "profit", "margin_pct", "revenue_share_pct"]]
        print(c_df.to_string(index=False, formatters={
            "revenue": "{:,.2f}".format,
            "profit": "{:,.2f}".format,
            "units_sold": "{:,.1f}".format,
            "margin_pct": "{:,.1f}%".format,
            "revenue_share_pct": "{:,.1f}%".format,
        }))

    print("\n[Payment Methods]")
    if not summary["payments"].empty:
        p_df = summary["payments"][["payment_label", "receipts", "revenue", "revenue_share_pct"]]
        print(p_df.to_string(index=False, formatters={
            "revenue": "{:,.2f}".format,
            "revenue_share_pct": "{:,.1f}%".format,
            "receipts": "{:,d}".format,
        }))

    print("\n[Day-of-Week Seasonality]")
    w_df = summary["weekdays"][["day", "days_count", "total_revenue", "avg_revenue", "total_receipts", "avg_aov"]]
    print(w_df.to_string(index=False, formatters={
        "total_revenue": "{:,.2f}".format,
        "avg_revenue": "{:,.2f}".format,
        "total_receipts": "{:,d}".format,
        "avg_aov": "{:,.2f}".format,
    }))

    print("\n[Top 5 Products by Revenue]")
    if not summary["top_products"].empty:
        tp_df = summary["top_products"].head(5)[["product_name", "category", "units_sold", "revenue", "margin_pct"]]
        print(tp_df.to_string(index=False, formatters={
            "revenue": "{:,.2f}".format,
            "units_sold": "{:,.1f}".format,
            "margin_pct": "{:,.1f}%".format,
        }))
    print("=" * 72)


def recap_sales_for_month(
    target_month: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    plot: bool = True,
    export_images: bool = False,
    export_dir: str = "exports",
    image_format: str = "png",
    sales_df: Optional[pd.DataFrame] = None,
    items_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint for notebooks or scripts to perform a monthly sales recap.

    Usage in notebook:
        from monthly_sales_recap import recap_sales_for_month
        summary = recap_sales_for_month("2026-05", export_images=True)
    """
    summary = get_monthly_sales_summary(target_month=target_month, sales=sales_df, items=items_df)

    if IN_IPYTHON:
        k = summary["kpis"]
        meta = summary["metadata"]

        if meta["cur_sales_count"] == 0:
            db_min_str = f"{meta['db_min_date']:%Y-%m-%d}" if meta["db_min_date"] is not None else "N/A"
            db_max_str = f"{meta['db_max_date']:%Y-%m-%d}" if meta["db_max_date"] is not None else "N/A"
            empty_warning = f"""
            <div style="background: #fffbeb; border: 1px solid #f59e0b; border-left: 5px solid #f59e0b;
                        color: #92400e; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; font-family: sans-serif;">
                <div style="font-weight: 700; font-size: 15px; margin-bottom: 4px;">⚠️ No sales found for {meta['month_label']}</div>
                <div style="font-size: 13px; color: #78350f;">
                    The database currently contains records from <strong>{db_min_str}</strong> to <strong>{db_max_str}</strong>.<br/>
                    <em>Tip: Try a month within the active period (e.g. <code>recap_sales_for_month("2026-05")</code>) or pass <code>recap_sales_for_month(None)</code> to automatically analyze the latest recorded month.</em>
                </div>
            </div>
            """
            display(HTML(empty_warning))

        def mom_badge(pct):
            if pct is None:
                return "<span style='color:#6b7280; font-size:12px;'>vs prev month: N/A</span>"
            color = "#10b981" if pct >= 0 else "#ef4444"
            arrow = "▲" if pct >= 0 else "▼"
            return f"<span style='color:{color}; font-weight:600; font-size:12px;'>{arrow} {abs(pct):.1f}% MoM</span>"

        html_card = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                    color: white; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px;">
                <div>
                    <h2 style="margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Monthly Sales Performance Recap</h2>
                    <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Period: <strong>{meta['month_label']}</strong> ({meta['cur_sales_count']:,} receipts, {k['days_in_month']} days)</p>
                </div>
                <div style="background: #6366f1; color: white; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">
                    Adminator Monthly Review
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                <div style="background: rgba(255,255,255,0.05); padding: 14px; border-radius: 8px; border: 1px solid #334155;">
                    <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Total Revenue</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0;">{k['revenue']:,.2f}</div>
                    {mom_badge(k['mom_revenue_pct'])}
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 14px; border-radius: 8px; border: 1px solid #334155;">
                    <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Gross Profit</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #34d399;">{k['gross_profit']:,.2f}</div>
                    <div>{mom_badge(k['mom_profit_pct'])} &bull; <span style="color:#cbd5e1; font-size:12px;">{k['gross_margin_pct']:.1f}% margin</span></div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 14px; border-radius: 8px; border: 1px solid #334155;">
                    <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Orders (Receipts)</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0;">{k['receipts']:,d}</div>
                    <div>{mom_badge(k['mom_receipts_pct'])} &bull; <span style="color:#cbd5e1; font-size:12px;">{k['daily_avg_receipts']:.1f}/day</span></div>
                </div>
                <div style="background: rgba(255,255,255,0.05); padding: 14px; border-radius: 8px; border: 1px solid #334155;">
                    <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Average Order Value</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #fbbf24;">{k['aov']:,.2f}</div>
                    <div>{mom_badge(k['mom_aov_pct'])} &bull; <span style="color:#cbd5e1; font-size:12px;">{k['units_sold']:,.0f} units</span></div>
                </div>
            </div>
        </div>
        """
        display(HTML(html_card))
    else:
        print_monthly_recap_terminal(summary)

    if plot and HAS_PLOTLY:
        figs = create_monthly_sales_figures(summary)
        if figs:
            fig_daily, fig_mix, fig_products, fig_weekdays = figs
            fig_daily.show()
            fig_mix.show()
            if fig_products:
                fig_products.show()
            fig_weekdays.show()

    if export_images:
        saved = export_monthly_sales_charts(summary, output_dir=export_dir, format=image_format)
        summary["exported_images"] = saved
        if IN_IPYTHON:
            paths_html = "".join([f"<li><strong>{name}:</strong> <code>{path}</code></li>" for name, path in saved.items()])
            display(HTML(f"""
            <div style="background: #f0fdf4; border: 1px solid #86efac; border-left: 5px solid #22c55e;
                        color: #15803d; padding: 12px 18px; border-radius: 8px; margin: 16px 0; font-family: sans-serif;">
                <div style="font-weight: 700; font-size: 14px;">✅ Monthly charts successfully exported to <code>{export_dir}/</code> ({len(saved)} images)</div>
                <ul style="margin: 6px 0 0 0; padding-left: 20px; font-size: 13px;">{paths_html}</ul>
            </div>
            """))
        else:
            print(f"\n[+] Exported {len(saved)} monthly chart images to {export_dir}/:")
            for name, path in saved.items():
                print(f"    - {name}: {path}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recap sales for a specified month.")
    parser.add_argument("--month", type=str, default=None, help="Target month (e.g. 2026-05, 2026-05-15, or leave empty for latest)")
    parser.add_argument("--export", action="store_true", help="Export charts to image files")
    parser.add_argument("--export-dir", type=str, default="exports", help="Directory to save exported images")
    parser.add_argument("--format", type=str, default="png", help="Image format (png, jpeg, pdf, svg)")
    args = parser.parse_args()
    recap_sales_for_month(
        target_month=args.month,
        plot=False,
        export_images=args.export,
        export_dir=args.export_dir,
        image_format=args.format,
    )
