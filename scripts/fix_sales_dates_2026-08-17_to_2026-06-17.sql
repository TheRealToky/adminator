-- Re-date sales: move every sale that occurred on 2026-08-17 -> 2026-06-17.
--
-- Target:
--   table  : sales_sale          (Django app "sales", model Sale)
--   column : occurred_at         (timestamptz, stored in UTC because USE_TZ=True)
--
-- "Done on 17 Aug 2026" is read in the BUSINESS timezone (Africa/Kigali, UTC+02:00,
-- no DST) -- the same offset the importer wrote (...T HH:MM:SS+02:00). We subtract
-- exactly two calendar months, so 17 Aug -> 17 Jun and each receipt keeps its
-- original wall-clock time of day (HH:MM:SS).
--
-- Wrapped in a transaction. RETURNING + the row count let you confirm the hit set
-- (24 rows at time of writing) before you keep it. To test without persisting,
-- replace COMMIT with ROLLBACK.
--
-- Run it:
--   docker exec -i adminator-scratch-postgres psql -U adminator -d adminator \
--     < scripts/fix_sales_dates_2026-08-17_to_2026-06-17.sql

BEGIN;

-- Make the month subtraction (and any ::date cast) resolve in business time.
SET LOCAL TimeZone = 'Africa/Kigali';

UPDATE sales_sale
SET    occurred_at = occurred_at - INTERVAL '1 day'
WHERE  (occurred_at AT TIME ZONE 'Africa/Kigali')::date = DATE '2026-07-22'
RETURNING id,
          receipt_number,
          occurred_at AS new_occurred_at;

COMMIT;
-- ROLLBACK;  -- use instead of COMMIT to dry-run
