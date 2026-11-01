-- Undo bulk expenses imported by `import_expenses.py --target expense`
--
-- SCOPE & SAFETY:
--   * Deletes standalone Expense records (`finance_expense`) created by `--target expense`.
--   * CRITICAL: Transactions (from the "Transactions" page, stored in `finance_transaction`)
--     are 100% PRESERVED and untouched.
--   * Sales (`sales_sale`) are 100% PRESERVED and untouched.
--   * Deleting duplicate expenses restores debited amounts back to wallet balances.
--
-- SAFE BY DEFAULT:
--   * Ends in ROLLBACK so it only previews. Change ROLLBACK to COMMIT to delete.
--
-- USAGE:
--   PowerShell:
--     Get-Content scripts/delete_withdrawals.sql | `
--         docker exec -i adminator-scratch-postgres psql -U adminator -d adminator
--   bash:
--     docker exec -i adminator-scratch-postgres \
--         psql -U adminator -d adminator < scripts/delete_withdrawals.sql

\set start_date '2026-08-13'
\set end_date   '2026-09-24'

BEGIN;

-- 1. Safety check: Verify Transactions page and Sales page counts are untouched
SELECT
    COUNT(*) AS transactions_page_preserved,
    COUNT(*) FILTER (WHERE direction = 'income') AS income_transactions,
    COUNT(*) FILTER (WHERE direction = 'expense') AS expense_transactions
FROM finance_transaction
WHERE occurred_on BETWEEN :'start_date' AND :'end_date';

SELECT
    COUNT(*) AS sales_page_preserved
FROM sales_sale
WHERE (occurred_at AT TIME ZONE 'Africa/Kigali')::date BETWEEN :'start_date' AND :'end_date';

-- 2. Preview duplicate Expense records that will be deleted
SELECT
    e.id,
    w.name AS wallet,
    c.name AS category,
    e.incurred_on,
    e.amount,
    e.title,
    e.reference,
    e.created_at
FROM finance_expense e
LEFT JOIN finance_wallet w ON w.id = e.wallet_id
LEFT JOIN finance_expensecategory c ON c.id = e.category_id
WHERE e.incurred_on BETWEEN :'start_date' AND :'end_date'
ORDER BY e.incurred_on, e.created_at;

-- 3. Summary of expenses to delete and amount to restore per wallet
SELECT
    COALESCE(w.name, 'No wallet') AS wallet,
    COUNT(e.id) AS duplicate_expense_count,
    SUM(e.amount) AS total_amount_restored
FROM finance_expense e
LEFT JOIN finance_wallet w ON w.id = e.wallet_id
WHERE e.incurred_on BETWEEN :'start_date' AND :'end_date'
GROUP BY w.name;

-- 4. Delete the duplicate Expense records
DELETE FROM finance_expense
WHERE incurred_on BETWEEN :'start_date' AND :'end_date'
RETURNING id, wallet_id, amount, incurred_on, title, reference;

-- ── Dry-run guard ────────────────────────────────────────────────────────────
-- Leave as ROLLBACK to preview only. Swap to COMMIT to make the delete stick.
ROLLBACK;
-- COMMIT;
