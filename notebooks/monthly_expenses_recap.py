"""
Monthly Expenses Recap Helper for Adminator Notebooks.

Allows analyzing, summarizing, and visualizing company expenses for any specified
calendar month using unified data loaded from db.py (both finance_expense
and expense transactions).
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

from db import load_expenses


PAYMENT_LABELS = {
    "cash": "Cash",
    "mobile_money": "Mobile Money",
    "card": "Card / POS",
    "bank_transfer": "Bank Transfer",
    "credit": "Credit / Account",
}

WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

# Categories excluded from the donut/pie chart display (still counted in KPIs and other charts)
EXCLUDED_PIE_CATEGORIES = {"Inventory write-off", "Change"}

# Maximum number of slices shown individually; everything beyond top-N is merged into "Others"
PIE_MAX_CATEGORIES = 6


def _collapse_pie_others(df: "pd.DataFrame", value_col: str = "amount", label_col: str = "category") -> "pd.DataFrame":
    """Keep the top PIE_MAX_CATEGORIES by value; merge the rest into a single 'Others' row."""
    df = df.sort_values(by=value_col, ascending=False).reset_index(drop=True)
    if len(df) <= PIE_MAX_CATEGORIES:
        return df
    top = df.iloc[:PIE_MAX_CATEGORIES].copy()
    others_val = df.iloc[PIE_MAX_CATEGORIES:][value_col].sum()
    others_row = {value_col: others_val, label_col: "Others"}
    return pd.concat([top, pd.DataFrame([others_row])], ignore_index=True).fillna(0)

def is_running_in_notebook() -> bool:
    """Check if the code is actually running inside an interactive Jupyter notebook."""
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ in ("ZMQInteractiveShell", "Shell")
    except Exception:
        return False


def parse_month_boundaries(
    target: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    expenses_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp, str, str, str]:
    """
    Determine the start and end timestamps for the target month and previous month.

    Args:
        target: Can be:
            - None: selects the month of the latest expense in expenses_df (or today).
            - '2026-08': Year-Month string format.
            - '2026-08-15' / date / Timestamp: extracts year and month.
        expenses_df: Optional expenses DataFrame to infer the latest date if target is None.

    Returns:
        (month_start, month_end, prev_month_start, prev_month_end, month_label, month_slug, month_title)
    """
    if target is None:
        if expenses_df is not None and not expenses_df.empty and "incurred_on" in expenses_df:
            ref_dt = expenses_df["incurred_on"].max()
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


def get_monthly_expenses_summary(
    target_month: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    expenses: Optional[pd.DataFrame] = None,
    source: str = "all",
) -> Dict[str, Any]:
    """
    Compute comprehensive monthly expense analytics, trends, and breakdowns.

    Args:
        target_month: '2026-08', date, or None for latest month with expenses.
        expenses: Optional pre-loaded expenses DataFrame.
        source: 'all' (default), 'transactions', or 'expenses'.

    Returns:
        A dictionary containing:
        - kpis: summary spend, counts, daily averages, and MoM changes
        - daily: day-by-day (1st to last day) spend, rolling avg, and counts
        - weekdays: performance aggregated by weekday (Monday to Sunday)
        - categories: category breakdown with total spend and share %
        - payments: payment method breakdown
        - top_expenses: top 10 largest expenses of the month
        - metadata: month boundaries, labels, and database active ranges
    """
    if expenses is None:
        expenses = load_expenses(source=source)

    expenses = expenses.copy()

    # Normalize numeric columns
    if "amount" in expenses.columns:
        expenses["amount"] = pd.to_numeric(expenses["amount"], errors="coerce").fillna(0.0)

    if "incurred_on" in expenses.columns:
        expenses["incurred_on"] = pd.to_datetime(expenses["incurred_on"])

    db_min = expenses["incurred_on"].min() if not expenses.empty else None
    db_max = expenses["incurred_on"].max() if not expenses.empty else None

    (
        m_start_naive,
        m_end_naive,
        prev_m_start_naive,
        prev_m_end_naive,
        month_label,
        month_slug,
        month_title,
    ) = parse_month_boundaries(target_month, expenses)

    # Timezone-aware handling
    tz = expenses["incurred_on"].dt.tz if not expenses.empty else None
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

    cur_exp = expenses[(expenses["incurred_on"] >= m_start) & (expenses["incurred_on"] <= m_end)].copy()
    prev_exp = expenses[(expenses["incurred_on"] >= prev_m_start) & (expenses["incurred_on"] <= prev_m_end)].copy()

    days_in_month = (m_end_naive.date() - m_start_naive.date()).days + 1

    # KPIs Calculation
    cur_total = float(cur_exp["amount"].sum()) if not cur_exp.empty else 0.0
    cur_count = int(len(cur_exp))
    cur_avg = (cur_total / cur_count) if cur_count > 0 else 0.0
    daily_avg = cur_total / days_in_month if days_in_month > 0 else 0.0

    prev_total = float(prev_exp["amount"].sum()) if not prev_exp.empty else 0.0
    prev_count = int(len(prev_exp))
    prev_avg = (prev_total / prev_count) if prev_count > 0 else 0.0

    def calc_mom(cur: float, prev: float) -> Optional[float]:
        if prev > 0:
            return ((cur - prev) / prev) * 100.0
        return None

    # 1. Full Daily Breakdown (1st through last day of month)
    month_dates = [m_start_naive.date() + datetime.timedelta(days=i) for i in range(days_in_month)]
    daily_base = pd.DataFrame({
        "date": month_dates,
        "day_num": [d.day for d in month_dates],
        "day": [d.strftime("%A") for d in month_dates],
    })

    if not cur_exp.empty:
        cur_exp["date"] = cur_exp["incurred_on"].dt.date
        daily_agg = (
            cur_exp.groupby("date")
            .agg(
                amount=("amount", "sum"),
                count=("id", "count"),
            )
            .reset_index()
        )
    else:
        daily_agg = pd.DataFrame({"date": pd.Series(dtype="object"), "amount": pd.Series(dtype="float64"), "count": pd.Series(dtype="int64")})

    daily = daily_base.merge(daily_agg, on="date", how="left")
    daily["amount"] = pd.to_numeric(daily["amount"], errors="coerce").fillna(0.0)
    daily["count"] = pd.to_numeric(daily["count"], errors="coerce").fillna(0).astype(int)
    daily["avg_per_entry"] = np.where(daily["count"] > 0, daily["amount"] / daily["count"], 0.0)
    daily["rolling7_amount"] = daily["amount"].rolling(7, min_periods=1).mean()
    daily["cumulative_amount"] = daily["amount"].cumsum()

    # 2. Weekday Seasonality Performance (Mon..Sun)
    weekdays = (
        daily.groupby("day")
        .agg(
            days_count=("date", "count"),
            total_amount=("amount", "sum"),
            avg_amount=("amount", "mean"),
            total_entries=("count", "sum"),
            avg_entries=("count", "mean"),
        )
        .reindex(WEEKDAY_ORDER)
        .reset_index()
    )
    weekdays["share_pct"] = (weekdays["total_amount"] / cur_total * 100.0) if cur_total > 0 else 0.0

    # 3. Category Breakdown
    if not cur_exp.empty:
        categories = (
            cur_exp.groupby("category")
            .agg(
                amount=("amount", "sum"),
                count=("id", "count"),
            )
            .reset_index()
        )
        categories["share_pct"] = (categories["amount"] / cur_total * 100.0) if cur_total > 0 else 0.0
        categories["avg_amount"] = categories["amount"] / categories["count"]
        categories = categories.sort_values(by="amount", ascending=False).reset_index(drop=True)
    else:
        categories = pd.DataFrame(columns=["category", "amount", "count", "share_pct", "avg_amount"])

    # 4. Payment Method Breakdown
    if not cur_exp.empty:
        payments = (
            cur_exp.groupby("payment_method")
            .agg(
                amount=("amount", "sum"),
                count=("id", "count"),
            )
            .reset_index()
        )
        payments["payment_label"] = payments["payment_method"].map(lambda p: PAYMENT_LABELS.get(p, str(p).replace("_", " ").capitalize()))
        payments["share_pct"] = (payments["amount"] / cur_total * 100.0) if cur_total > 0 else 0.0
        payments = payments.sort_values(by="amount", ascending=False).reset_index(drop=True)
    else:
        payments = pd.DataFrame(columns=["payment_method", "payment_label", "amount", "count", "share_pct"])

    # 5. Top 10 Individual Expenses
    if not cur_exp.empty:
        top_expenses = cur_exp.sort_values(by="amount", ascending=False).head(10).copy()
        top_expenses["share_pct"] = (top_expenses["amount"] / cur_total * 100.0) if cur_total > 0 else 0.0
        top_expenses["date_str"] = top_expenses["incurred_on"].dt.strftime("%Y-%m-%d")
        top_expenses = top_expenses[["title", "category", "amount", "payment_method", "date_str", "share_pct", "reference"]].reset_index(drop=True)
    else:
        top_expenses = pd.DataFrame(columns=["title", "category", "amount", "payment_method", "date_str", "share_pct", "reference"])

    top_cat = categories.iloc[0]["category"] if not categories.empty else "None"
    top_cat_share = float(categories.iloc[0]["share_pct"]) if not categories.empty else 0.0

    kpis = {
        "total_expenses": cur_total,
        "expense_count": cur_count,
        "avg_expense": cur_avg,
        "daily_avg_expense": daily_avg,
        "days_in_month": days_in_month,
        "top_category": top_cat,
        "top_category_share": top_cat_share,
        "prev_total": prev_total,
        "prev_count": prev_count,
        "prev_avg": prev_avg,
        "mom_total_pct": calc_mom(cur_total, prev_total),
        "mom_count_pct": calc_mom(cur_count, prev_count),
        "mom_avg_pct": calc_mom(cur_avg, prev_avg),
    }

    return {
        "kpis": kpis,
        "daily": daily,
        "weekdays": weekdays,
        "categories": categories,
        "payments": payments,
        "top_expenses": top_expenses,
        "metadata": {
            "month_label": month_label,
            "month_title": month_title,
            "month_slug": month_slug,
            "start_date": m_start_naive,
            "end_date": m_end_naive,
            "days_in_month": days_in_month,
            "cur_count": cur_count,
            "db_min_date": db_min,
            "db_max_date": db_max,
            "source": source,
        },
    }


def create_monthly_expenses_figures(summary: Dict[str, Any]):
    """Generate interactive Plotly dashboard charts for monthly expenses."""
    if not HAS_PLOTLY:
        return None

    daily = summary["daily"]
    categories = summary["categories"]
    payments = summary["payments"]
    weekdays = summary["weekdays"]
    top_exp = summary["top_expenses"]
    meta = summary["metadata"]

    # ── Figure 1: Daily Spend & 7-Day Moving Average ──────────────────────────
    fig_daily = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Daily Expenses & 7-day Avg ({meta['month_title']})",
            "Daily Expense Count & Average Size"
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": True}]],
    )

    fig_daily.add_trace(
        go.Bar(
            x=daily["date"],
            y=daily["amount"],
            name="Daily Spend",
            marker_color="#e11d48",  # vibrant rose
            opacity=0.85,
        ),
        row=1, col=1,
    )
    fig_daily.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["rolling7_amount"],
            name="7-Day Moving Avg",
            mode="lines",
            line=dict(color="#f97316", width=2.5),
        ),
        row=1, col=1,
    )

    # Col 2: Entries Count bars + Avg size line
    fig_daily.add_trace(
        go.Bar(
            x=daily["date"],
            y=daily["count"],
            name="Entries Count",
            marker_color="#6366f1",  # indigo
            opacity=0.75,
            legend="legend2",
        ),
        row=1, col=2, secondary_y=False,
    )
    fig_daily.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["avg_per_entry"],
            name="Avg per Entry",
            mode="lines+markers",
            marker=dict(size=5, color="#10b981"),
            line=dict(width=2, color="#10b981"),
            legend="legend2",
        ),
        row=1, col=2, secondary_y=True,
    )

    fig_daily.update_layout(
        height=450,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.05,
            xanchor="left", x=0.0,
        ),
        legend2=dict(
            orientation="h", yanchor="bottom", y=1.05,
            xanchor="right", x=1.0,
        ),
        template="plotly_white",
    )
    fig_daily.update_yaxes(title_text="Amount (RWF)", row=1, col=1)
    fig_daily.update_yaxes(title_text="Entries Count", row=1, col=2, secondary_y=False)
    fig_daily.update_yaxes(title_text="Avg per Entry", row=1, col=2, secondary_y=True)

    # ── Figure 2: Category & Payment Breakdown (Separate Top-Right Legends) ───
    fig_mix = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=("Expenses by Category", "Expenses by Payment Method"),
        horizontal_spacing=0.18,
    )

    color_palette = ["#e11d48", "#f97316", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4", "#64748b"]

    # Filter out categories that should not appear on the donut chart
    cat_pie = _collapse_pie_others(
        categories[~categories["category"].isin(EXCLUDED_PIE_CATEGORIES)].copy()
    )

    if not cat_pie.empty:
        fig_mix.add_trace(
            go.Pie(
                labels=cat_pie["category"],
                values=cat_pie["amount"],
                hole=0.45,
                name="Category",
                legend="legend",
                textinfo="percent",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>Spend: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
                marker_colors=color_palette,
            ),
            row=1, col=1,
        )

    if not payments.empty:
        fig_mix.add_trace(
            go.Pie(
                labels=payments["payment_label"],
                values=payments["amount"],
                hole=0.45,
                name="Payment",
                legend="legend2",
                textinfo="percent",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>Spend: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
                marker_colors=["#06b6d4", "#10b981", "#f97316", "#6366f1", "#a855f7"],
            ),
            row=1, col=2,
        )

    # Offset donut circles so both top-right legends have room
    if len(fig_mix.data) >= 1:
        fig_mix.data[0].domain = dict(x=[0.0, 0.30], y=[0.0, 1.0])
    if len(fig_mix.data) >= 2:
        fig_mix.data[1].domain = dict(x=[0.50, 0.80], y=[0.0, 1.0])

    fig_mix.update_layout(
        height=380,
        margin=dict(l=20, r=160, t=50, b=20),
        legend=dict(
            title_text="<b>Categories</b>",
            x=0.33,
            y=1.0,
            xanchor="left",
            yanchor="top",
            orientation="v",
            font=dict(size=11),
        ),
        legend2=dict(
            title_text="<b>Payment Methods</b>",
            x=0.82,
            y=1.0,
            xanchor="left",
            yanchor="top",
            orientation="v",
            font=dict(size=11),
        ),
        template="plotly_white",
    )

    # ── Figure 3: Top 10 Largest Expense Items ───────────────────────────────
    if not top_exp.empty:
        top_sorted = top_exp.sort_values(by="amount", ascending=True)
        fig_top = go.Figure(
            go.Bar(
                x=top_sorted["amount"],
                y=top_sorted["title"],
                orientation="h",
                marker_color="#e11d48",
                text=top_sorted.apply(
                    lambda r: f"{r['amount']:,.0f} ({r['category']}) &bull; {r['date_str']}",
                    axis=1,
                ),
                textposition="auto",
            )
        )
        fig_top.update_layout(
            title=f"Top 10 Expenses ({meta['month_title']})",
            xaxis_title="Amount (RWF)",
            yaxis_title="",
            height=420,
            margin=dict(l=150, r=40, t=60, b=40),
            template="plotly_white",
        )
    else:
        fig_top = None

    # ── Figure 4: Day-of-Week Seasonality Performance ────────────────────────
    fig_weekdays = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Average Daily Spend by Day of Week", "Total Entries by Day of Week"),
    )
    fig_weekdays.add_trace(
        go.Bar(
            x=weekdays["day"],
            y=weekdays["avg_amount"],
            name="Avg Spend",
            marker_color="#e11d48",
            text=weekdays["avg_amount"].map(lambda v: f"{v:,.0f}"),
            textposition="auto",
        ),
        row=1, col=1,
    )
    fig_weekdays.add_trace(
        go.Bar(
            x=weekdays["day"],
            y=weekdays["total_entries"],
            name="Total Entries",
            marker_color="#6366f1",
            text=weekdays["total_entries"].map(lambda v: f"{v:,d}"),
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

    return fig_daily, fig_mix, fig_top, fig_weekdays


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
    top_exp = summary["top_expenses"]
    meta = summary["metadata"]

    # 1. Daily Expenses Trend
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
    ax1.bar(daily["day_num"], daily["amount"], label="Daily Spend", color="#e11d48", alpha=0.75)
    ax1.plot(daily["day_num"], daily["rolling7_amount"], label="7-Day Avg", color="#f97316", linewidth=2.5)
    ax1.set_title(f"Daily Expenses & 7-day Avg ({meta['month_title']})", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Day of Month")
    ax1.set_ylabel("Amount (RWF)")
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2_twin = ax2.twinx()
    ax2.bar(daily["day_num"], daily["count"], color="#6366f1", alpha=0.7, label="Entries")
    ax2_twin.plot(daily["day_num"], daily["avg_per_entry"], color="#10b981", marker="o", markersize=4, linewidth=2, label="Avg Size")
    ax2.set_title("Daily Entries & Average Size", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Day of Month")
    ax2.set_ylabel("Entries")
    ax2_twin.set_ylabel("Avg Amount")
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Add combined legend for both ax2 and ax2_twin
    lines_1, labels_1 = ax2.get_legend_handles_labels()
    lines_2, labels_2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    plt.tight_layout()
    p1 = os.path.join(output_dir, f"01_monthly_daily_expenses_{month_slug}.{format}")
    fig.savefig(p1, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["daily_expenses"] = p1

    # 2. Category & Payment Mix
    fig, (ax_c, ax_p) = plt.subplots(1, 2, figsize=(14, 5))
    cat_pie_mpl = _collapse_pie_others(
        categories[~categories["category"].isin(EXCLUDED_PIE_CATEGORIES)].copy()
    )
    if not cat_pie_mpl.empty:
        wedges_c, _, _ = ax_c.pie(
            cat_pie_mpl["amount"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#e11d48", "#f97316", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"],
            textprops=dict(color="white", weight="bold", size=9),
        )
        ax_c.legend(
            wedges_c, cat_pie_mpl["category"], title="Categories",
            loc="upper right", bbox_to_anchor=(1.25, 1.0), fontsize=9
        )
        ax_c.set_title("Expenses by Category", fontsize=12, fontweight="bold")

    if not payments.empty:
        wedges_p, _, _ = ax_p.pie(
            payments["amount"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#06b6d4", "#10b981", "#f97316", "#6366f1", "#a855f7"],
            textprops=dict(color="white", weight="bold", size=9),
        )
        ax_p.legend(
            wedges_p, payments["payment_label"], title="Payment Methods",
            loc="upper right", bbox_to_anchor=(1.28, 1.0), fontsize=9
        )
        ax_p.set_title("Expenses by Payment Method", fontsize=12, fontweight="bold")

    plt.tight_layout()
    p2 = os.path.join(output_dir, f"02_monthly_expense_categories_payment_{month_slug}.{format}")
    fig.savefig(p2, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["categories_payment_mix"] = p2

    # 3. Top 10 Expenses
    if not top_exp.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        sorted_top = top_exp.sort_values(by="amount", ascending=True)
        ax.barh(sorted_top["title"], sorted_top["amount"], color="#e11d48")
        ax.set_title(f"Top 10 Expenses ({meta['month_title']})", fontsize=12, fontweight="bold")
        ax.set_xlabel("Amount (RWF)")
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        p3 = os.path.join(output_dir, f"03_monthly_top_expenses_{month_slug}.{format}")
        fig.savefig(p3, dpi=200, bbox_inches="tight")
        plt.close(fig)
        saved_files["top_expenses"] = p3

    # 4. Weekday Seasonality
    fig, (ax_w1, ax_w2) = plt.subplots(1, 2, figsize=(14, 5))
    ax_w1.bar(weekdays["day"], weekdays["avg_amount"], color="#e11d48")
    ax_w1.set_title("Average Daily Spend by Day of Week", fontsize=12, fontweight="bold")
    ax_w1.set_xticks(range(len(weekdays["day"])))
    ax_w1.set_xticklabels(weekdays["day"], rotation=25)
    ax_w1.grid(True, linestyle="--", alpha=0.5)

    ax_w2.bar(weekdays["day"], weekdays["total_entries"], color="#6366f1")
    ax_w2.set_title("Total Entries by Day of Week", fontsize=12, fontweight="bold")
    ax_w2.set_xticks(range(len(weekdays["day"])))
    ax_w2.set_xticklabels(weekdays["day"], rotation=25)
    ax_w2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    p4 = os.path.join(output_dir, f"04_monthly_expense_weekday_performance_{month_slug}.{format}")
    fig.savefig(p4, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["weekday_performance"] = p4

    return saved_files


def export_monthly_expenses_charts(
    summary: Dict[str, Any],
    output_dir: str = "exports",
    format: str = "png",
    scale: int = 2,
) -> Dict[str, str]:
    """Export all monthly expense charts to static image files."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    meta = summary["metadata"]
    month_slug = meta["month_slug"]
    saved_files = {}

    figs = create_monthly_expenses_figures(summary)
    exported_via_plotly = False

    if figs and HAS_PLOTLY:
        fig_daily, fig_mix, fig_top, fig_weekdays = figs
        try:
            p1 = os.path.join(output_dir, f"01_monthly_daily_expenses_{month_slug}.{format}")
            fig_daily.write_image(p1, format=format, scale=scale, width=1200, height=500)
            saved_files["daily_expenses"] = p1

            p2 = os.path.join(output_dir, f"02_monthly_expense_categories_payment_{month_slug}.{format}")
            fig_mix.write_image(p2, format=format, scale=scale, width=1000, height=450)
            saved_files["categories_payment_mix"] = p2

            if fig_top:
                p3 = os.path.join(output_dir, f"03_monthly_top_expenses_{month_slug}.{format}")
                fig_top.write_image(p3, format=format, scale=scale, width=1000, height=500)
                saved_files["top_expenses"] = p3

            p4 = os.path.join(output_dir, f"04_monthly_expense_weekday_performance_{month_slug}.{format}")
            fig_weekdays.write_image(p4, format=format, scale=scale, width=1100, height=450)
            saved_files["weekday_performance"] = p4

            exported_via_plotly = True
        except Exception:
            exported_via_plotly = False

    if not exported_via_plotly:
        saved_files = _export_charts_matplotlib(summary, output_dir=output_dir, format=format, month_slug=month_slug)

    return saved_files


def print_monthly_expenses_terminal(summary: Dict[str, Any]):
    """Pretty-print monthly expense recap for terminal or plain console."""
    k = summary["kpis"]
    meta = summary["metadata"]
    print("=" * 72)
    print(f"  MONTHLY EXPENSES RECAP: {meta['month_label']}")
    print("=" * 72)

    def mom_str(pct):
        if pct is None:
            return "N/A (no prior month)"
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}% MoM"

    print(f" Total Expenses:      {k['total_expenses']:>15,.2f}  ({mom_str(k['mom_total_pct'])})")
    print(f" Total Entries:       {k['expense_count']:>15,d}  ({mom_str(k['mom_count_pct'])})")
    print(f" Avg per Entry:       {k['avg_expense']:>15,.2f}  ({mom_str(k['mom_avg_pct'])})")
    print(f" Daily Avg Spend:     {k['daily_avg_expense']:>15,.2f}")
    print(f" Top Category:        {k['top_category']} ({k['top_category_share']:.1f}% of total)")
    print("-" * 72)

    print("\n[Expenses by Category]")
    if not summary["categories"].empty:
        c_df = summary["categories"][["category", "amount", "count", "share_pct", "avg_amount"]]
        print(c_df.to_string(index=False, formatters={
            "amount": "{:,.2f}".format,
            "avg_amount": "{:,.2f}".format,
            "count": "{:,d}".format,
            "share_pct": "{:,.1f}%".format,
        }))

    print("\n[Day-of-Week Seasonality]")
    w_df = summary["weekdays"][["day", "days_count", "total_amount", "avg_amount", "total_entries"]]
    print(w_df.to_string(index=False, formatters={
        "total_amount": "{:,.2f}".format,
        "avg_amount": "{:,.2f}".format,
        "total_entries": "{:,d}".format,
    }))

    print("\n[Top 5 Expenses]")
    if not summary["top_expenses"].empty:
        top_df = summary["top_expenses"].head(5)[["title", "category", "amount", "payment_method", "date_str"]]
        print(top_df.to_string(index=False, formatters={
            "amount": "{:,.2f}".format,
        }))
    print("=" * 72)


def recap_expenses_for_month(
    target_month: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    plot: bool = True,
    export_images: bool = False,
    export_dir: str = "exports",
    image_format: str = "png",
    expenses_df: Optional[pd.DataFrame] = None,
    source: str = "all",
) -> Dict[str, Any]:
    """
    Main entrypoint for monthly expenses recap.

    Usage in notebook:
        from monthly_expenses_recap import recap_expenses_for_month
        summary = recap_expenses_for_month("2026-08", export_images=True)
    """
    summary = get_monthly_expenses_summary(target_month=target_month, expenses=expenses_df, source=source)

    in_nb = is_running_in_notebook()

    if in_nb and IN_IPYTHON:
        k = summary["kpis"]
        meta = summary["metadata"]

        if meta["cur_count"] == 0:
            db_min_str = f"{meta['db_min_date']:%Y-%m-%d}" if meta["db_min_date"] is not None else "N/A"
            db_max_str = f"{meta['db_max_date']:%Y-%m-%d}" if meta["db_max_date"] is not None else "N/A"
            empty_warning = f"""
            <div style="background: #fffbeb; border: 1px solid #f59e0b; border-left: 5px solid #f59e0b;
                        color: #92400e; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; font-family: sans-serif;">
                <div style="font-weight: 700; font-size: 15px; margin-bottom: 4px;">⚠️ No expenses found for {meta['month_label']}</div>
                <div style="font-size: 13px; color: #78350f;">
                    The database currently contains expenses from <strong>{db_min_str}</strong> to <strong>{db_max_str}</strong>.<br/>
                    <em>Tip: Try an active month (e.g. <code>recap_expenses_for_month("2026-08")</code>) or pass <code>recap_expenses_for_month(None)</code> to automatically analyze the latest recorded month.</em>
                </div>
            </div>
            """
            display(HTML(empty_warning))

        def mom_badge(pct):
            if pct is None:
                return "<span style='color:#6b7280; font-size:12px;'>vs prev month: N/A</span>"
            color = "#ef4444" if pct > 0 else ("#10b981" if pct < 0 else "#6b7280")
            arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
            return f"<span style='color:{color}; font-weight:600; font-size:12px;'>{arrow} {abs(pct):.1f}% MoM</span>"

        html_card = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
                    color: white; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #4338ca; padding-bottom: 12px; margin-bottom: 16px;">
                <div>
                    <h2 style="margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Monthly Expenses Performance Recap</h2>
                    <p style="margin: 4px 0 0 0; color: #cbd5e1; font-size: 13px;">Period: <strong>{meta['month_label']}</strong> ({meta['cur_count']:,} expense entries, {k['days_in_month']} days)</p>
                </div>
                <div style="background: #e11d48; color: white; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">
                    Adminator Expense Review
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Total Expenses</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #f43f5e;">{k['total_expenses']:,.2f}</div>
                    {mom_badge(k['mom_total_pct'])}
                </div>
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Expense Entries</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0;">{k['expense_count']:,d}</div>
                    <div>{mom_badge(k['mom_count_pct'])} &bull; <span style="color:#94a3b8; font-size:12px;">{(k['expense_count']/float(k['days_in_month'])):.1f}/day</span></div>
                </div>
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Daily Avg Spend</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #fbbf24;">{k['daily_avg_expense']:,.2f}</div>
                    <div style="color:#94a3b8; font-size:12px;">across {k['days_in_month']} calendar days</div>
                </div>
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Top Category</div>
                    <div style="font-size: 20px; font-weight: 700; margin: 4px 0; color: #a78bfa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{k['top_category']}</div>
                    <div style="color:#cbd5e1; font-size:12px;">{k['top_category_share']:.1f}% of total spend</div>
                </div>
            </div>
        </div>
        """
        display(HTML(html_card))
    else:
        print_monthly_expenses_terminal(summary)

    if plot and HAS_PLOTLY:
        figs = create_monthly_expenses_figures(summary)
        if figs:
            fig_daily, fig_mix, fig_top, fig_weekdays = figs
            fig_daily.show()
            fig_mix.show()
            if fig_top:
                fig_top.show()
            fig_weekdays.show()

    if export_images:
        saved = export_monthly_expenses_charts(summary, output_dir=export_dir, format=image_format)
        summary["exported_images"] = saved
        if in_nb and IN_IPYTHON:
            paths_html = "".join([f"<li><strong>{name}:</strong> <code>{path}</code></li>" for name, path in saved.items()])
            display(HTML(f"""
            <div style="background: #f0fdf4; border: 1px solid #86efac; border-left: 5px solid #22c55e;
                        color: #15803d; padding: 12px 18px; border-radius: 8px; margin: 16px 0; font-family: sans-serif;">
                <div style="font-weight: 700; font-size: 14px;">✅ Monthly expense charts exported to <code>{export_dir}/</code> ({len(saved)} images)</div>
                <ul style="margin: 6px 0 0 0; padding-left: 20px; font-size: 13px;">{paths_html}</ul>
            </div>
            """))
        else:
            print(f"\n[+] Exported {len(saved)} monthly expense chart images to {export_dir}/:")
            for name, path in saved.items():
                print(f"    - {name}: {path}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recap expenses for a specified month.")
    parser.add_argument("--month", type=str, default=None, help="Target month (e.g. 2026-08, 2026-08-15, or leave empty for latest)")
    parser.add_argument("--source", type=str, default="all", choices=["all", "transactions", "expenses"], help="Data source filter")
    parser.add_argument("--export", action="store_true", help="Export charts to image files")
    parser.add_argument("--export-dir", type=str, default="exports", help="Directory to save exported images")
    parser.add_argument("--format", type=str, default="png", help="Image format (png, jpeg, pdf, svg)")
    args = parser.parse_args()
    recap_expenses_for_month(
        target_month=args.month,
        plot=False,
        export_images=args.export,
        export_dir=args.export_dir,
        image_format=args.format,
        source=args.source,
    )
