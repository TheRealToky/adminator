"""
Weekly Expenses Recap Helper for Adminator Notebooks.

Allows analyzing, summarizing, and visualizing company expenses for any specified
week (Monday through Sunday) using unified data loaded from db.py (both finance_expense
and expense transactions).
"""
from __future__ import annotations

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
    import pandas as _pd
    return _pd.concat([top, _pd.DataFrame([others_row])], ignore_index=True).fillna(0)

def parse_week_boundaries(
    target: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    expenses_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp, str, str, str]:
    """
    Determine the start (Monday 00:00:00) and end (Sunday 23:59:59.999999) of the target
    and previous weeks.

    Args:
        target: Can be:
            - None: selects the week of the latest expense recorded in expenses_df (or today).
            - '2026-W32' or '2026-32': ISO week format.
            - '2026-08-10' / date / Timestamp: extracts week containing this date.
        expenses_df: Optional expenses DataFrame to infer the latest date if target is None.

    Returns:
        (week_start, week_end, prev_week_start, prev_week_end, week_label, week_slug, week_title)
    """
    if target is None:
        if expenses_df is not None and not expenses_df.empty and "incurred_on" in expenses_df:
            ref_dt = expenses_df["incurred_on"].max()
            if hasattr(ref_dt, "tz") and ref_dt.tz is not None:
                ref_dt = ref_dt.tz_localize(None)
        else:
            ref_dt = pd.Timestamp.now()
        cal = ref_dt.isocalendar()
        year, week = int(cal.year), int(cal.week)
        base_monday = datetime.date.fromisocalendar(year, week, 1)
    elif isinstance(target, str) and ("-W" in target.upper() or (len(target) == 7 and target[4] == "-")):
        clean_target = target.upper().replace("-W", "-")
        parts = clean_target.split("-")
        year, week = int(parts[0]), int(parts[1])
        base_monday = datetime.date.fromisocalendar(year, week, 1)
    else:
        dt = pd.to_datetime(target)
        if hasattr(dt, "tz") and dt.tz is not None:
            dt = dt.tz_localize(None)
        cal = dt.isocalendar()
        year, week = int(cal.year), int(cal.week)
        base_monday = datetime.date.fromisocalendar(year, week, 1)

    week_start = pd.Timestamp(base_monday.year, base_monday.month, base_monday.day, 0, 0, 0)
    week_end = week_start + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

    prev_week_start = week_start - pd.Timedelta(days=7)
    prev_week_end = week_end - pd.Timedelta(days=7)

    week_title = f"{year}-W{week:02d}"
    week_label = f"Week {week:02d}, {year} ({week_start:%b %d} – {week_end:%b %d, %Y})"
    week_slug = f"{year}_W{week:02d}"

    return week_start, week_end, prev_week_start, prev_week_end, week_label, week_slug, week_title


def get_weekly_expenses_summary(
    target_week: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    expenses: Optional[pd.DataFrame] = None,
    source: str = "all",
) -> Dict[str, Any]:
    """
    Compute comprehensive weekly expense metrics and breakdowns.

    Args:
        target_week: ISO week string (e.g. '2026-W32'), date string ('2026-08-10'), or None.
        expenses: Optional pre-loaded expenses DataFrame.
        source: 'all' (default), 'transactions', or 'expenses'.

    Returns:
        A dictionary containing:
        - kpis: summary spend, counts, daily averages, and WoW changes
        - daily: day-by-day (Mon..Sun) spend and transaction count
        - categories: category breakdown with total spend and share %
        - payments: payment method breakdown
        - top_expenses: top 10 largest expenses of the week
        - metadata: week boundaries, labels, and database active ranges
    """
    if expenses is None:
        expenses = load_expenses(source=source)

    expenses = expenses.copy()

    # Normalize numeric columns
    if "amount" in expenses.columns:
        expenses["amount"] = pd.to_numeric(expenses["amount"], errors="coerce").fillna(0.0)

    # Ensure date column exists
    if "incurred_on" in expenses.columns:
        expenses["incurred_on"] = pd.to_datetime(expenses["incurred_on"])

    db_min = expenses["incurred_on"].min() if not expenses.empty else None
    db_max = expenses["incurred_on"].max() if not expenses.empty else None

    (
        w_start_naive,
        w_end_naive,
        prev_w_start_naive,
        prev_w_end_naive,
        week_label,
        week_slug,
        week_title,
    ) = parse_week_boundaries(target_week, expenses)

    # Timezone-aware handling
    tz = expenses["incurred_on"].dt.tz if not expenses.empty else None
    if tz is not None:
        w_start = w_start_naive.tz_localize(tz) if w_start_naive.tz is None else w_start_naive.tz_convert(tz)
        w_end = w_end_naive.tz_localize(tz) if w_end_naive.tz is None else w_end_naive.tz_convert(tz)
        prev_w_start = prev_w_start_naive.tz_localize(tz) if prev_w_start_naive.tz is None else prev_w_start_naive.tz_convert(tz)
        prev_w_end = prev_w_end_naive.tz_localize(tz) if prev_w_end_naive.tz is None else prev_w_end_naive.tz_convert(tz)
    else:
        w_start = w_start_naive.tz_localize(None) if w_start_naive.tz is not None else w_start_naive
        w_end = w_end_naive.tz_localize(None) if w_end_naive.tz is not None else w_end_naive
        prev_w_start = prev_w_start_naive.tz_localize(None) if prev_w_start_naive.tz is not None else prev_w_start_naive
        prev_w_end = prev_w_end_naive.tz_localize(None) if prev_w_end_naive.tz is not None else prev_w_end_naive

    cur_exp = expenses[(expenses["incurred_on"] >= w_start) & (expenses["incurred_on"] <= w_end)].copy()
    prev_exp = expenses[(expenses["incurred_on"] >= prev_w_start) & (expenses["incurred_on"] <= prev_w_end)].copy()

    # KPI computations
    cur_total = float(cur_exp["amount"].sum()) if not cur_exp.empty else 0.0
    cur_count = int(len(cur_exp))
    cur_avg = (cur_total / cur_count) if cur_count > 0 else 0.0
    daily_avg = cur_total / 7.0

    prev_total = float(prev_exp["amount"].sum()) if not prev_exp.empty else 0.0
    prev_count = int(len(prev_exp))
    prev_avg = (prev_total / prev_count) if prev_count > 0 else 0.0

    def calc_wow(cur: float, prev: float) -> Optional[float]:
        if prev > 0:
            return ((cur - prev) / prev) * 100.0
        return None

    # 1. Daily Breakdown (Mon..Sun)
    week_dates = [w_start_naive.date() + datetime.timedelta(days=i) for i in range(7)]
    daily_base = pd.DataFrame({
        "date": week_dates,
        "day": [d.strftime("%A") for d in week_dates],
        "day_num": [d.day for d in week_dates],
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

    # 2. Category Breakdown
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

    # 3. Payment Method Breakdown
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

    # 4. Top 10 Individual Expenses
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
        "top_category": top_cat,
        "top_category_share": top_cat_share,
        "prev_total": prev_total,
        "prev_count": prev_count,
        "prev_avg": prev_avg,
        "wow_total_pct": calc_wow(cur_total, prev_total),
        "wow_count_pct": calc_wow(cur_count, prev_count),
        "wow_avg_pct": calc_wow(cur_avg, prev_avg),
    }

    return {
        "kpis": kpis,
        "daily": daily,
        "categories": categories,
        "payments": payments,
        "top_expenses": top_expenses,
        "metadata": {
            "week_label": week_label,
            "week_title": week_title,
            "week_slug": week_slug,
            "start_date": w_start_naive,
            "end_date": w_end_naive,
            "cur_count": cur_count,
            "db_min_date": db_min,
            "db_max_date": db_max,
            "source": source,
        },
    }


def create_weekly_expenses_figures(summary: Dict[str, Any]):
    """Generate clean Plotly dashboards for weekly expenses with separate top-right legends."""
    if not HAS_PLOTLY:
        return None

    daily = summary["daily"]
    categories = summary["categories"]
    payments = summary["payments"]
    top_exp = summary["top_expenses"]
    meta = summary["metadata"]

    # ── Figure 1: Daily Expense Amount & Voucher Count ────────────────────────
    fig_daily = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Daily Expenses ({meta['week_title']})",
            "Daily Expense Count & Average Size"
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": True}]],
    )
    fig_daily.add_trace(
        go.Bar(
            x=daily["day"],
            y=daily["amount"],
            name="Daily Spend",
            marker_color="#e11d48",  # vibrant rose/red
            opacity=0.85,
            text=daily["amount"].map(lambda v: f"{v:,.0f}" if v > 0 else ""),
            textposition="auto",
        ),
        row=1, col=1,
    )

    # Average line across the 7 days
    mean_val = summary["kpis"]["daily_avg_expense"]
    fig_daily.add_trace(
        go.Scatter(
            x=daily["day"],
            y=[mean_val] * 7,
            name="Daily Avg",
            mode="lines",
            line=dict(color="#f97316", width=2, dash="dash"),
        ),
        row=1, col=1,
    )

    # Col 2: Count bars + Avg size line
    fig_daily.add_trace(
        go.Bar(
            x=daily["day"],
            y=daily["count"],
            name="Entries Count",
            marker_color="#6366f1",  # indigo
            opacity=0.75,
            text=daily["count"].map(lambda v: f"{v:d}" if v > 0 else ""),
            textposition="auto",
            legend="legend2",
        ),
        row=1, col=2, secondary_y=False,
    )
    fig_daily.add_trace(
        go.Scatter(
            x=daily["day"],
            y=daily["avg_per_entry"],
            name="Avg per Entry",
            mode="lines+markers",
            marker=dict(size=6, color="#10b981"),
            line=dict(width=2.5, color="#10b981"),
            legend="legend2",
        ),
        row=1, col=2, secondary_y=True,
    )

    fig_daily.update_layout(
        height=430,
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
    fig_daily.update_yaxes(title_text="Entries", row=1, col=2, secondary_y=False)
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
            title=f"Top 10 Expenses ({meta['week_title']})",
            xaxis_title="Amount (RWF)",
            yaxis_title="",
            height=420,
            margin=dict(l=150, r=40, t=60, b=40),
            template="plotly_white",
        )
    else:
        fig_top = None

    # ── Figure 4: Category Breakdown Bar Chart (Spend & Share %) ─────────────
    if not categories.empty:
        cat_sorted = categories.sort_values(by="amount", ascending=True)
        fig_cat_bar = go.Figure(
            go.Bar(
                x=cat_sorted["amount"],
                y=cat_sorted["category"],
                orientation="h",
                marker_color="#6366f1",
                text=cat_sorted.apply(lambda r: f"{r['amount']:,.0f} ({r['share_pct']:.1f}%)", axis=1),
                textposition="auto",
            )
        )
        fig_cat_bar.update_layout(
            title=f"Category Spend Breakdown ({meta['week_title']})",
            xaxis_title="Amount (RWF)",
            yaxis_title="",
            height=380,
            margin=dict(l=140, r=40, t=60, b=40),
            template="plotly_white",
        )
    else:
        fig_cat_bar = None

    return fig_daily, fig_mix, fig_top, fig_cat_bar


def _export_charts_matplotlib(
    summary: Dict[str, Any], output_dir: str, format: str, week_slug: str
) -> Dict[str, str]:
    """Fallback high-resolution exporter using Matplotlib."""
    import os
    import matplotlib.pyplot as plt

    saved_files = {}
    daily = summary["daily"]
    categories = summary["categories"]
    payments = summary["payments"]
    top_exp = summary["top_expenses"]
    meta = summary["metadata"]

    # 1. Daily Expenses
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
    ax1.bar(daily["day"], daily["amount"], color="#e11d48", alpha=0.8, label="Daily Spend")
    mean_val = summary["kpis"]["daily_avg_expense"]
    ax1.axhline(mean_val, color="#f97316", linestyle="--", linewidth=2, label="Daily Avg")
    ax1.set_title(f"Daily Expenses ({meta['week_title']})", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Amount (RWF)")
    ax1.set_xticks(range(len(daily["day"])))
    ax1.set_xticklabels(daily["day"], rotation=25)
    ax1.legend()
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2_twin = ax2.twinx()
    ax2.bar(daily["day"], daily["count"], color="#6366f1", alpha=0.75, label="Entries")
    ax2_twin.plot(daily["day"], daily["avg_per_entry"], color="#10b981", marker="o", linewidth=2, label="Avg/Entry")
    ax2.set_title("Daily Entries & Average Size", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Entries Count")
    ax2_twin.set_ylabel("Avg Amount")
    ax2.set_xticks(range(len(daily["day"])))
    ax2.set_xticklabels(daily["day"], rotation=25)
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Add combined legend for both ax2 and ax2_twin
    lines_1, labels_1 = ax2.get_legend_handles_labels()
    lines_2, labels_2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    plt.tight_layout()
    p1 = os.path.join(output_dir, f"01_weekly_daily_expenses_{week_slug}.{format}")
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
    p2 = os.path.join(output_dir, f"02_weekly_expense_categories_payment_{week_slug}.{format}")
    fig.savefig(p2, dpi=200, bbox_inches="tight")
    plt.close(fig)
    saved_files["categories_payment_mix"] = p2

    # 3. Top 10 Expenses
    if not top_exp.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        sorted_top = top_exp.sort_values(by="amount", ascending=True)
        ax.barh(sorted_top["title"], sorted_top["amount"], color="#e11d48")
        ax.set_title(f"Top 10 Expenses ({meta['week_title']})", fontsize=12, fontweight="bold")
        ax.set_xlabel("Amount (RWF)")
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        p3 = os.path.join(output_dir, f"03_weekly_top_expenses_{week_slug}.{format}")
        fig.savefig(p3, dpi=200, bbox_inches="tight")
        plt.close(fig)
        saved_files["top_expenses"] = p3

    # 4. Category Spend Bar Chart
    if not categories.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        cat_sorted = categories.sort_values(by="amount", ascending=True)
        ax.barh(cat_sorted["category"], cat_sorted["amount"], color="#6366f1")
        ax.set_title(f"Category Spend Breakdown ({meta['week_title']})", fontsize=12, fontweight="bold")
        ax.set_xlabel("Amount (RWF)")
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        p4 = os.path.join(output_dir, f"04_weekly_category_spend_{week_slug}.{format}")
        fig.savefig(p4, dpi=200, bbox_inches="tight")
        plt.close(fig)
        saved_files["category_spend"] = p4

    return saved_files


def export_weekly_expenses_charts(
    summary: Dict[str, Any],
    output_dir: str = "exports",
    format: str = "png",
    scale: int = 2,
) -> Dict[str, str]:
    """Export all weekly expense charts to static image files."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    meta = summary["metadata"]
    week_slug = meta["week_slug"]
    saved_files = {}

    figs = create_weekly_expenses_figures(summary)
    exported_via_plotly = False

    if figs and HAS_PLOTLY:
        fig_daily, fig_mix, fig_top, fig_cat = figs
        try:
            p1 = os.path.join(output_dir, f"01_weekly_daily_expenses_{week_slug}.{format}")
            fig_daily.write_image(p1, format=format, scale=scale, width=1200, height=480)
            saved_files["daily_expenses"] = p1

            p2 = os.path.join(output_dir, f"02_weekly_expense_categories_payment_{week_slug}.{format}")
            fig_mix.write_image(p2, format=format, scale=scale, width=1000, height=450)
            saved_files["categories_payment_mix"] = p2

            if fig_top:
                p3 = os.path.join(output_dir, f"03_weekly_top_expenses_{week_slug}.{format}")
                fig_top.write_image(p3, format=format, scale=scale, width=1000, height=480)
                saved_files["top_expenses"] = p3

            if fig_cat:
                p4 = os.path.join(output_dir, f"04_weekly_category_spend_{week_slug}.{format}")
                fig_cat.write_image(p4, format=format, scale=scale, width=1000, height=450)
                saved_files["category_spend"] = p4

            exported_via_plotly = True
        except Exception:
            exported_via_plotly = False

    if not exported_via_plotly:
        saved_files = _export_charts_matplotlib(summary, output_dir=output_dir, format=format, week_slug=week_slug)

    return saved_files


def print_weekly_expenses_terminal(summary: Dict[str, Any]):
    """Pretty-print weekly expense recap in terminal or plain text."""
    k = summary["kpis"]
    meta = summary["metadata"]
    print("=" * 72)
    print(f"  WEEKLY EXPENSES RECAP: {meta['week_label']}")
    print("=" * 72)

    def wow_str(pct):
        if pct is None:
            return "N/A (no prior week)"
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}% WoW"

    print(f" Total Expenses:      {k['total_expenses']:>15,.2f}  ({wow_str(k['wow_total_pct'])})")
    print(f" Total Entries:       {k['expense_count']:>15,d}  ({wow_str(k['wow_count_pct'])})")
    print(f" Avg per Entry:       {k['avg_expense']:>15,.2f}  ({wow_str(k['wow_avg_pct'])})")
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

    print("\n[Daily Breakdown (Mon - Sun)]")
    d_df = summary["daily"][["day", "date", "amount", "count", "avg_per_entry"]]
    print(d_df.to_string(index=False, formatters={
        "amount": "{:,.2f}".format,
        "avg_per_entry": "{:,.2f}".format,
        "count": "{:,d}".format,
    }))

    print("\n[Top 5 Expenses]")
    if not summary["top_expenses"].empty:
        top_df = summary["top_expenses"].head(5)[["title", "category", "amount", "payment_method", "date_str"]]
        print(top_df.to_string(index=False, formatters={
            "amount": "{:,.2f}".format,
        }))
    print("=" * 72)


def recap_expenses_for_week(
    target_week: Optional[Union[str, datetime.date, datetime.datetime, pd.Timestamp]] = None,
    plot: bool = True,
    export_images: bool = False,
    export_dir: str = "exports",
    image_format: str = "png",
    expenses_df: Optional[pd.DataFrame] = None,
    source: str = "all",
) -> Dict[str, Any]:
    """
    Main entrypoint for weekly expense recap.

    Usage in notebook:
        from weekly_expenses_recap import recap_expenses_for_week
        summary = recap_expenses_for_week("2026-W32", export_images=True)
    """
    summary = get_weekly_expenses_summary(target_week=target_week, expenses=expenses_df, source=source)

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
                <div style="font-weight: 700; font-size: 15px; margin-bottom: 4px;">⚠️ No expenses found for {meta['week_label']}</div>
                <div style="font-size: 13px; color: #78350f;">
                    The database currently contains expenses from <strong>{db_min_str}</strong> to <strong>{db_max_str}</strong>.<br/>
                    <em>Tip: Try an active week (e.g. <code>recap_expenses_for_week("2026-W32")</code>) or pass <code>recap_expenses_for_week(None)</code> to automatically analyze the latest recorded week.</em>
                </div>
            </div>
            """
            display(HTML(empty_warning))

        def wow_badge(pct):
            if pct is None:
                return "<span style='color:#6b7280; font-size:12px;'>vs prev week: N/A</span>"
            # For expenses, an increase is typically red, decrease is green
            color = "#ef4444" if pct > 0 else ("#10b981" if pct < 0 else "#6b7280")
            arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
            return f"<span style='color:{color}; font-weight:600; font-size:12px;'>{arrow} {abs(pct):.1f}% WoW</span>"

        html_card = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
                    color: white; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #4338ca; padding-bottom: 12px; margin-bottom: 16px;">
                <div>
                    <h2 style="margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Weekly Expenses Performance Recap</h2>
                    <p style="margin: 4px 0 0 0; color: #cbd5e1; font-size: 13px;">Period: <strong>{meta['week_label']}</strong> ({meta['cur_count']:,} expense entries)</p>
                </div>
                <div style="background: #e11d48; color: white; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">
                    Adminator Expense Review
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Total Expenses</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #f43f5e;">{k['total_expenses']:,.2f}</div>
                    {wow_badge(k['wow_total_pct'])}
                </div>
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Expense Entries</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0;">{k['expense_count']:,d}</div>
                    <div>{wow_badge(k['wow_count_pct'])} &bull; <span style="color:#94a3b8; font-size:12px;">{(k['expense_count']/7.0):.1f}/day</span></div>
                </div>
                <div style="background: rgba(255,255,255,0.06); padding: 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Daily Avg Spend</div>
                    <div style="font-size: 24px; font-weight: 700; margin: 4px 0; color: #fbbf24;">{k['daily_avg_expense']:,.2f}</div>
                    <div style="color:#94a3b8; font-size:12px;">across 7 calendar days</div>
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
        print_weekly_expenses_terminal(summary)

    if plot and HAS_PLOTLY:
        figs = create_weekly_expenses_figures(summary)
        if figs:
            fig_daily, fig_mix, fig_top, fig_cat = figs
            fig_daily.show()
            fig_mix.show()
            if fig_top:
                fig_top.show()
            if fig_cat:
                fig_cat.show()

    if export_images:
        saved = export_weekly_expenses_charts(summary, output_dir=export_dir, format=image_format)
        summary["exported_images"] = saved
        if in_nb and IN_IPYTHON:
            paths_html = "".join([f"<li><strong>{name}:</strong> <code>{path}</code></li>" for name, path in saved.items()])
            display(HTML(f"""
            <div style="background: #f0fdf4; border: 1px solid #86efac; border-left: 5px solid #22c55e;
                        color: #15803d; padding: 12px 18px; border-radius: 8px; margin: 16px 0; font-family: sans-serif;">
                <div style="font-weight: 700; font-size: 14px;">✅ Weekly expense charts exported to <code>{export_dir}/</code> ({len(saved)} images)</div>
                <ul style="margin: 6px 0 0 0; padding-left: 20px; font-size: 13px;">{paths_html}</ul>
            </div>
            """))
        else:
            print(f"\n[+] Exported {len(saved)} weekly expense chart images to {export_dir}/:")
            for name, path in saved.items():
                print(f"    - {name}: {path}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recap expenses for a specified week.")
    parser.add_argument("--week", type=str, default=None, help="Target week (e.g. 2026-W32, 2026-08-10, or leave empty for latest)")
    parser.add_argument("--source", type=str, default="all", choices=["all", "transactions", "expenses"], help="Data source filter")
    parser.add_argument("--export", action="store_true", help="Export charts to image files")
    parser.add_argument("--export-dir", type=str, default="exports", help="Directory to save exported images")
    parser.add_argument("--format", type=str, default="png", help="Image format (png, jpeg, pdf, svg)")
    args = parser.parse_args()
    recap_expenses_for_week(
        target_week=args.week,
        plot=False,
        export_images=args.export,
        export_dir=args.export_dir,
        image_format=args.format,
        source=args.source,
    )
