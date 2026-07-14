-- Delete a specific *withdrawal* WalletEntry by description, date, and amount.
--
-- Targets the withdrawal (entry_type='withdrawal') whose description matches
-- :description, that occurred on :occurred_on, with amount :amount. Only
-- withdrawals are touched — deposits, transfers, and the money flows from
-- sales/expenses/transactions live in other tables and are never affected.
-- Wallet balances are derived live, so deleting the row updates the balance with
-- no further bookkeeping.
--
-- Safe by default: the script ends in ROLLBACK, so it only *previews*. To
-- actually delete, change the final ROLLBACK to COMMIT.
--
-- Run from the repo root on the host.
--   PowerShell (Windows) — the '<' redirect does not work, so pipe instead:
--     Get-Content scripts/delete_withdrawal.sql | `
--         docker exec -i adminator-scratch-postgres psql -U adminator -d adminator
--   bash/sh:
--     docker exec -i adminator-scratch-postgres \
--         psql -U adminator -d adminator < scripts/delete_withdrawal.sql
--
-- Edit :description / :occurred_on / :amount below to target a different entry
-- (description is matched case-insensitively).

\set description 'Daily readjustment'
\set occurred_on '2026-06-29'
\set amount 4900

BEGIN;

-- What matches (there should be exactly one — check before committing):
SELECT e.id, w.name AS wallet, e.amount, e.occurred_on, e.created_at, e.description
FROM finance_walletentry e
JOIN finance_wallet w ON w.id = e.wallet_id
WHERE e.entry_type = 'withdrawal'
  AND lower(e.description) = lower(:'description')
  AND e.occurred_on = :'occurred_on'
  AND e.amount = :amount
ORDER BY e.created_at DESC;

DELETE FROM finance_walletentry
WHERE entry_type = 'withdrawal'
  AND lower(description) = lower(:'description')
  AND occurred_on = :'occurred_on'
  AND amount = :amount
RETURNING id, amount, occurred_on, description;

-- ── Dry-run guard ────────────────────────────────────────────────────────────
-- Leave as ROLLBACK to preview only. Swap to COMMIT to make the delete stick.
ROLLBACK;
-- COMMIT;
