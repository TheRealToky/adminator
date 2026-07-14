-- Sum of all sales and transactions tagged to one wallet on a single day.
--
-- Reports, for the given wallet and day:
--   sales_in       = SUM(sales_sale.total)          where wallet matches
--   tx_income      = SUM(finance_transaction.amount) direction='income'
--   tx_expense     = SUM(finance_transaction.amount) direction='expense'
--   net            = sales_in + tx_income - tx_expense
-- plus a per-row breakdown so you can eyeball what made up each total.
--
-- These are the sales/transaction slices of what Wallet.current_balance folds
-- together (see apps/finance/models.py). Wallet entries (deposits/withdrawals/
-- transfers) and expenses also move the balance but are NOT counted here — this
-- script answers "sales and transactions" specifically.
--
-- Date bucketing:
--   sales_sale.occurred_at is timestamptz (UTC), so it's converted to the
--   shop-local calendar day (Africa/Kigali, UTC+2, no DST) to match the
--   reports. finance_transaction.occurred_on is already a local DateField, so
--   it's compared directly.
--
-- Read-only — no BEGIN/COMMIT needed.
--
-- Run from the repo root on the host.
--   PowerShell (Windows) — the '<' redirect does not work, so pipe instead:
--     Get-Content scripts/wallet_day_sales_transactions.sql | `
--         docker exec -i adminator-scratch-postgres psql -U adminator -d adminator
--   bash/sh:
--     docker exec -i adminator-scratch-postgres \
--         psql -U adminator -d adminator < scripts/wallet_day_sales_transactions.sql
--
-- Edit :wallet_name / :day below (wallet name is matched case-insensitively).

\set wallet_name 'Mobile money balance'
\set day '2026-07-01'
\set business_tz 'Africa/Kigali'

-- ── Summary: one row with the day's totals for this wallet ──────────────────
WITH w AS (
    SELECT id, name FROM finance_wallet
    WHERE lower(name) = lower(:'wallet_name')
),
sales AS (
    SELECT COALESCE(SUM(s.total), 0) AS sales_in
    FROM sales_sale s
    JOIN w ON w.id = s.wallet_id
    WHERE (s.occurred_at AT TIME ZONE :'business_tz')::date = :'day'
),
tx AS (
    SELECT
        COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'income'), 0)  AS tx_income,
        COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'expense'), 0) AS tx_expense
    FROM finance_transaction t
    JOIN w ON w.id = t.wallet_id
    WHERE t.occurred_on = :'day'
)
SELECT
    (SELECT name FROM w)          AS wallet,
    :'day'::date                  AS day,
    sales.sales_in,
    tx.tx_income,
    tx.tx_expense,
    sales.sales_in + tx.tx_income - tx.tx_expense AS net
FROM sales, tx;

-- ── Breakdown: every sale and transaction that fed the totals above ─────────
WITH w AS (
    SELECT id, name FROM finance_wallet
    WHERE lower(name) = lower(:'wallet_name')
)
SELECT 'sale' AS kind,
       s.receipt_number       AS ref,
       NULL                   AS direction,
       s.total                AS amount,
       (s.occurred_at AT TIME ZONE :'business_tz') AS occurred_at_local
FROM sales_sale s
JOIN w ON w.id = s.wallet_id
WHERE (s.occurred_at AT TIME ZONE :'business_tz')::date = :'day'

UNION ALL

SELECT 'transaction' AS kind,
       t.title        AS ref,
       t.direction    AS direction,
       t.amount       AS amount,
       t.created_at   AS occurred_at_local
FROM finance_transaction t
JOIN w ON w.id = t.wallet_id
WHERE t.occurred_on = :'day'

ORDER BY occurred_at_local;
