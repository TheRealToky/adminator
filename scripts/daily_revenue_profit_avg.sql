-- Daily revenue and profit, plus their averages over a date range.
--
-- Mirrors the formula scripts/reports/report_common.py uses (revenue() /
-- cogs()), so numbers here should match what daily_report.py prints:
--   revenue = SUM(sales_sale.total)
--   profit  = SUM(sales_sale.total) - SUM(sales_sale.cost_of_goods)
-- (Gross profit only — no other income/expenses folded in, same as the
-- report's "gross_profit", not its "net_profit".)
--
-- Days are bucketed by shop-local calendar day (Africa/Kigali, UTC+2, no
-- DST) since occurred_at is stored as timestamptz in UTC. Days with zero
-- sales are included via generate_series so the average is a true
-- per-calendar-day average, not just an average over days that had sales.
--
-- Read-only — no BEGIN/COMMIT needed.
--
-- Run from the repo root on the host:
--     docker exec -i adminator-scratch-postgres \
--         psql -U adminator -d adminator < scripts/reports/daily_revenue_profit_avg.sql
--
-- Edit the date range below as needed.

\set start_date '2026-06-10'
\set end_date '2026-07-01'
\set business_tz 'Africa/Kigali'

WITH days AS (
    SELECT generate_series(:'start_date'::date, :'end_date'::date, interval '1 day')::date AS sale_day
),
sales_by_day AS (
    SELECT
        (occurred_at AT TIME ZONE :'business_tz')::date AS sale_day,
        SUM(total) AS revenue,
        SUM(cost_of_goods) AS cogs
    FROM sales_sale
    WHERE (occurred_at AT TIME ZONE :'business_tz')::date BETWEEN :'start_date' AND :'end_date'
    GROUP BY 1
),
daily AS (
    SELECT
        d.sale_day,
        COALESCE(s.revenue, 0) AS revenue,
        COALESCE(s.cogs, 0) AS cogs,
        COALESCE(s.revenue, 0) - COALESCE(s.cogs, 0) AS profit
    FROM days d
    LEFT JOIN sales_by_day s USING (sale_day)
)

-- Per-day breakdown:
SELECT
    sale_day,
    revenue,
    cogs,
    profit,
    ROUND(CASE WHEN revenue = 0 THEN NULL ELSE profit / revenue * 100 END, 2) AS margin_pct
FROM daily
ORDER BY sale_day;

-- Averages over the whole range (edit the CTE above, then re-run just this
-- query if you only want the summary):
WITH days AS (
    SELECT generate_series(:'start_date'::date, :'end_date'::date, interval '1 day')::date AS sale_day
),
sales_by_day AS (
    SELECT
        (occurred_at AT TIME ZONE :'business_tz')::date AS sale_day,
        SUM(total) AS revenue,
        SUM(cost_of_goods) AS cogs
    FROM sales_sale
    WHERE (occurred_at AT TIME ZONE :'business_tz')::date BETWEEN :'start_date' AND :'end_date'
    GROUP BY 1
),
daily AS (
    SELECT
        d.sale_day,
        COALESCE(s.revenue, 0) AS revenue,
        COALESCE(s.cogs, 0) AS cogs,
        COALESCE(s.revenue, 0) - COALESCE(s.cogs, 0) AS profit
    FROM days d
    LEFT JOIN sales_by_day s USING (sale_day)
)
SELECT
    COUNT(*) AS days_in_range,
    COUNT(*) FILTER (WHERE revenue > 0) AS days_with_sales,
    ROUND(AVG(revenue), 2) AS avg_daily_revenue,
    ROUND(AVG(profit), 2) AS avg_daily_profit,
    ROUND(SUM(revenue), 2) AS total_revenue,
    ROUND(SUM(profit), 2) AS total_profit
FROM daily;
