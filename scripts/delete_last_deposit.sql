-- Delete the most recent *deposit* from a wallet (default: Petite caisse).
--
-- "Last deposit" = entry_type='deposit' with the latest occurred_on, then the
-- latest created_at (the same order the Wallets page history shows first). Only
-- deposits are touched — withdrawals, transfers, and the money flows from
-- sales/expenses/transactions live in other tables and are never affected.
-- Wallet balances are derived live, so deleting the row updates the balance with
-- no further bookkeeping.
--
-- Safe by default: the script ends in ROLLBACK, so it only *previews*. To
-- actually delete, change the final ROLLBACK to COMMIT.
--
-- Run from the repo root on the host:
--     docker exec -i adminator-scratch-postgres \
--         psql -U adminator -d adminator < scripts/delete_last_deposit.sql
--
-- Different wallet: edit :wallet_name below (matched case-insensitively).

\set wallet_name 'Petite caisse'

BEGIN;

-- What would be deleted (newest deposit on this wallet):
SELECT e.id, e.amount, e.occurred_on, e.created_at, e.description
FROM finance_walletentry e
JOIN finance_wallet w ON w.id = e.wallet_id
WHERE e.entry_type = 'deposit'
  AND lower(w.name) = lower(:'wallet_name')
ORDER BY e.occurred_on DESC, e.created_at DESC
LIMIT 1;

-- Postgres DELETE has no ORDER BY/LIMIT, so target the row by id via a subquery.
DELETE FROM finance_walletentry
WHERE id = (
    SELECT e.id
    FROM finance_walletentry e
    JOIN finance_wallet w ON w.id = e.wallet_id
    WHERE e.entry_type = 'deposit'
      AND lower(w.name) = lower(:'wallet_name')
    ORDER BY e.occurred_on DESC, e.created_at DESC
    LIMIT 1
)
RETURNING id, amount, occurred_on, description;

-- ── Dry-run guard ────────────────────────────────────────────────────────────
-- Leave as ROLLBACK to preview only. Swap to COMMIT to make the delete stick.
ROLLBACK;
-- COMMIT;
