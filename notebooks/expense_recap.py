"""
Unified Expense Recap Module for Adminator Notebooks.

Provides both weekly and monthly expense analysis, KPI computation,
interactive visualization, and image export capabilities:

Usage in a Jupyter Notebook:
    # 1. Weekly recap
    from expense_recap import recap_expenses_for_week
    week_summary = recap_expenses_for_week("2026-W32", export_images=True)

    # 2. Monthly recap
    from expense_recap import recap_expenses_for_month
    month_summary = recap_expenses_for_month("2026-08", export_images=True)
"""
from __future__ import annotations

from weekly_expenses_recap import (
    parse_week_boundaries,
    get_weekly_expenses_summary,
    create_weekly_expenses_figures,
    export_weekly_expenses_charts,
    recap_expenses_for_week,
)

from monthly_expenses_recap import (
    parse_month_boundaries,
    get_monthly_expenses_summary,
    create_monthly_expenses_figures,
    export_monthly_expenses_charts,
    recap_expenses_for_month,
)

__all__ = [
    "parse_week_boundaries",
    "get_weekly_expenses_summary",
    "create_weekly_expenses_figures",
    "export_weekly_expenses_charts",
    "recap_expenses_for_week",
    "parse_month_boundaries",
    "get_monthly_expenses_summary",
    "create_monthly_expenses_figures",
    "export_monthly_expenses_charts",
    "recap_expenses_for_month",
]
