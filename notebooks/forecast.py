"""
Simple revenue / profit / cash-on-hand forecasting model for the pastry shop.

Built on top of the existing `get_engine` / `load_sales` / `load_expenses`
helpers (assumed to live in the same module, e.g. `adminator_data.py`).
Import both in a notebook cell:

    from adminator_data import load_sales, load_expenses
    from forecast import DailyHistory, forecast_day, forecast_cash

The model is intentionally simple: it's a weekday-seasonality-adjusted
moving average, not a "real" time series model (no ARIMA/Prophet/etc).
That's enough to answer "roughly how much will we sell / have in the
till on date X" without needing months of clean history first.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# 1. Build a clean daily history from raw sales + expenses
# --------------------------------------------------------------------------

@dataclass
class DailyHistory:
    """Daily revenue / profit / expenses / net cash flow, one row per day."""
    daily: pd.DataFrame          # index=date, columns=[revenue, profit, expenses, net]
    weekday_index: pd.Series     # index=0..6 (Mon..Sun), multiplier vs. overall daily mean
    trend_per_day: float         # RWF/day drift, fit on the last `trend_window` days


def build_daily_history(
    sales: pd.DataFrame,
    expenses: pd.DataFrame,
    trend_window: int = 60,
) -> DailyHistory:
    """
    sales: output of load_sales() -> needs occurred_at, total, cost_of_goods
    expenses: output of load_expenses() -> needs incurred_on, amount
    """
    s = sales.copy()
    s["day"] = pd.to_datetime(s["occurred_at"]).dt.date
    daily_sales = s.groupby("day").agg(
        revenue=("total", "sum"),
        cost_of_goods=("cost_of_goods", "sum"),
    )
    daily_sales["profit"] = daily_sales["revenue"] - daily_sales["cost_of_goods"]

    e = expenses.copy()
    e["day"] = pd.to_datetime(e["incurred_on"]).dt.date
    daily_expenses = e.groupby("day").agg(expenses=("amount", "sum"))

    # Full calendar range so missing days (shop closed, no data yet) show as 0
    # rather than silently disappearing from the average.
    start = min(daily_sales.index.min(), daily_expenses.index.min())
    end = max(daily_sales.index.max(), daily_expenses.index.max())
    full_range = pd.date_range(start, end, freq="D").date

    daily = pd.DataFrame(index=full_range)
    daily = daily.join(daily_sales, how="left").join(daily_expenses, how="left")
    daily[["revenue", "cost_of_goods", "profit", "expenses"]] = daily[
        ["revenue", "cost_of_goods", "profit", "expenses"]
    ].fillna(0.0)
    daily["net"] = daily["profit"] - daily["expenses"]

    # Weekday seasonality: e.g. Saturdays might sell 1.4x an average day.
    weekday = pd.Series(daily.index).apply(lambda d: d.weekday())
    daily["weekday"] = weekday.values
    overall_mean = daily["revenue"].mean()
    weekday_means = daily.groupby("weekday")["revenue"].mean()
    weekday_index = (weekday_means / overall_mean).reindex(range(7)).fillna(1.0)

    # Trend: simple linear fit of revenue over the last `trend_window` days,
    # so a shop that's growing/shrinking isn't stuck at a flat historical
    # average forever.
    recent = daily.tail(trend_window)
    if len(recent) >= 2:
        x = np.arange(len(recent))
        slope, _ = np.polyfit(x, recent["revenue"].values, 1)
    else:
        slope = 0.0

    return DailyHistory(daily=daily.drop(columns="weekday"), weekday_index=weekday_index, trend_per_day=slope)


# --------------------------------------------------------------------------
# 2. Forecast a single day's revenue / profit / expenses
# --------------------------------------------------------------------------

def forecast_day(
    history: DailyHistory,
    target_date: date,
    lookback_days: int = 30,
    use_trend: bool = True,
) -> dict:
    """
    Forecast revenue/profit/expenses/net for one specific date.

    Method: trailing `lookback_days` average, adjusted for that date's
    weekday (e.g. Saturdays tend to sell more than Tuesdays), optionally
    nudged by the recent linear trend.
    """
    recent = history.daily.tail(lookback_days)
    avg_revenue = recent["revenue"].mean()
    avg_profit_margin = (recent["profit"].sum() / recent["revenue"].sum()) if recent["revenue"].sum() else 0.0
    avg_expenses = recent["expenses"].mean()

    weekday = target_date.weekday()
    seasonal_mult = history.weekday_index.get(weekday, 1.0)

    days_out = (target_date - recent.index.max()).days if len(recent) else 0
    trend_adjustment = history.trend_per_day * days_out if use_trend else 0.0

    revenue = max(0.0, avg_revenue * seasonal_mult + trend_adjustment)
    profit = revenue * avg_profit_margin
    expenses = avg_expenses  # expenses generally don't follow weekday sales seasonality
    net = profit - expenses

    return {
        "date": target_date,
        "forecast_revenue": round(revenue, 2),
        "forecast_profit": round(profit, 2),
        "forecast_expenses": round(expenses, 2),
        "forecast_net": round(net, 2),
        "weekday_seasonality_multiplier": round(seasonal_mult, 3),
        "lookback_days": lookback_days,
        "days_out_from_data": days_out,
    }


# --------------------------------------------------------------------------
# 3. Forecast cumulative cash available by a target date
# --------------------------------------------------------------------------

def forecast_cash(
    history: DailyHistory,
    target_date: date,
    current_cash: float,
    as_of_date: Optional[date] = None,
    lookback_days: int = 30,
    use_trend: bool = True,
) -> pd.DataFrame:
    """
    Project a running cash balance from `as_of_date` (default: the day
    after the last day in the data) through `target_date`, day by day,
    starting from `current_cash` (the actual cash on hand today).

    Returns a DataFrame indexed by date with columns:
        forecast_revenue, forecast_profit, forecast_expenses,
        forecast_net, cash_balance
    """
    if as_of_date is None:
        as_of_date = history.daily.index.max() + timedelta(days=1)
    if target_date < as_of_date:
        raise ValueError("target_date must be on or after as_of_date")

    rows = []
    running_cash = current_cash
    for d in pd.date_range(as_of_date, target_date, freq="D").date:
        day_fc = forecast_day(history, d, lookback_days=lookback_days, use_trend=use_trend)
        running_cash += day_fc["forecast_net"]
        day_fc["cash_balance"] = round(running_cash, 2)
        rows.append(day_fc)

    return pd.DataFrame(rows).set_index("date")


# --------------------------------------------------------------------------
# Example usage in a notebook cell
# --------------------------------------------------------------------------
#
# from adminator_data import load_sales, load_expenses
# from forecast import build_daily_history, forecast_day, forecast_cash
# from datetime import date
#
# sales = load_sales()
# expenses = load_expenses()
# history = build_daily_history(sales, expenses)
#
# # Single-day snapshot:
# forecast_day(history, date(2026, 10, 15))
#
# # Running cash projection from today to a target date:
# CURRENT_CASH_ON_HAND = 1_250_000  # RWF, pull from your actual till/bank count
# forecast_cash(history, date(2026, 10, 31), current_cash=CURRENT_CASH_ON_HAND)
