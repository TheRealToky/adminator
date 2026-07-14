# Migration Plan: Cash → Accrual (Double-Entry General Ledger)

**Status:** In progress — Phases 1–4 (partial) + Phase 6 UI (read **and** write controls) implemented.
**Scope decision:** Full double-entry general ledger (chart of accounts + balanced journal entries).
**Goals:** Accurate accrual P&L · Receivables & payables · Tax / external reporting · Balance sheet.

> ## Implementation status (see §7 for the full phase plan)
>
> Built and verified in an **isolated sandbox stack** (`docker-compose.accrual.yml`,
> project `adminator-accrual`) that shares no database, volume, network or ports
> with the main / scratch stacks:
>
> | Area | State |
> |---|---|
> | Ledger core (`Account`, `AccountingPeriod`, `JournalEntry`, `JournalLine`) | ✅ Done — balanced-entry invariant, idempotent source posting, reversal, period locking |
> | Chart of accounts (§3) | ✅ Seeded via `seed_chart_of_accounts` |
> | Posting rules — Sale (cash / **credit→A/R**), COGS, Expense, Transaction | ✅ Shadow mode via signals (`LEDGER_SHADOW_MODE`) |
> | Posting rules — **Invoice → A/R** (revenue at issuance, cumulative settlement) | ✅ Shadow mode via signals; integrates the previously-disconnected `Invoice` |
> | Posting rules — **Expense on credit → A/P** (`on_credit`/`settled_at`), plus bill settlement | ✅ Shadow mode via signals |
> | Posting rules — **inventory value**: raw purchase → A/P, waste → materials waste, stock adjustments | ✅ Stand-alone `StockMovement` / `ProcessedMaterialStockMovement` reasons |
> | Posting rules — **production & processed batches** (raw/processed → finished/processed inventory) | ✅ Valued at document level from the recipe (`ProductionRun`, `ProcessedMaterialBatch`) |
> | Posting rules — **monthly depreciation** (Dr 5300 · Cr 1590, straight-line) | ✅ `post_depreciation` rule + `post_depreciation` command (idempotent per asset+month) |
> | Backfill (`resync_ledger`) + opening balances (`post_opening_balances`) | ✅ Backfill now also covers stock moves, production runs and batches |
> | Reports — trial balance, income statement, balance sheet | ✅ Services + read API under `/api/v1/ledger/` |
> | **Phase 6 — Ledger UI** (`/ledger`) | ✅ Reports + chart of accounts + journal drill-down, **plus** a Periods tab (close/reopen) and a manual balanced-journal-entry modal (`POST /ledger/journal-entries/manual/`); nav entry under Finance; en/fr i18n |
> | Tests | ✅ 32 ledger tests green (A/P, inventory, production/batch, depreciation, manual-entry validation); full backend suite (61) green |
> | **Verified on seeded data:** trial balance & balance sheet both balance (difference 0.00) after a full `resync_ledger` that posts ~11k inventory moves, 93 runs and 4 batches. |
>
> **Known valuation caveat:** finished-goods inventory (1220) can run negative
> in the backfill because COGS relieves stock at the snapshotted `cost_of_goods`
> (which folds in overhead) while production capitalises only the actual
> raw+processed input cost, and a full replay relieves pre-cutover sales whose
> production was never posted. The GL still balances — the gap lands in retained
> earnings — but perpetual finished-goods valuation needs the §5.1 decision
> (weighted-average + an overhead-absorption account) before Phase 5 cutover.
>
> **Not yet wired** (deferred, see §4–§5): asset-purchase *capitalisation*
> (Dr 1500 instead of expensing — until then depreciation double-counts against
> an asset's `linked_expense`), automatic settlement of raw-purchase A/P (raw
> receipts credit A/P but carry no payment link yet), deferred revenue for
> customer deposits, tax on sales, and the Phase 5 cutover that points the live
> dashboard/`Wallet.current_balance` at the GL and makes it authoritative.
>
> **Run the sandbox:** `./scripts/accrual.ps1 up` (or `docker compose -f
> docker-compose.yml -f docker-compose.accrual.yml up -d`) → backend on
> **:8002**, frontend **:5175**, postgres **:5434**. Tests: `./scripts/accrual.ps1 test`.

---

## 1. Where we are today (the starting point)

The finance layer is **cash-derived aggregation** — there is no ledger. Numbers are computed on
the fly from domain rows:

| Concern | Today | Accrual gap |
|---|---|---|
| Revenue | `Sale.total` counted at `occurred_at` | Credit sales (`payment_method="credit"`) are recognized as revenue **and** flow into the wallet as if cash arrived. |
| Cash on hand | `Wallet.current_balance` sums sales + expenses + transactions + entries live | A credit sale wrongly increases the wallet; no separation of "earned" vs "collected". |
| Expenses | `Expense.incurred_on`, recognized when recorded | No prepaid / accrued split; no supplier payable (AP). |
| Receivables | `Invoice` exists (amount, amount_paid, due_date, `balance_due`) | **Disconnected** — analytics ignore invoices entirely; no GL link. |
| COGS | Snapshotted per `SaleItem.unit_cost` at sale time | Already matching-correct ✅ — good foundation. |
| Inventory | Perpetual quantity ledgers (`StockMovement`, `ProcessedMaterialStockMovement`) | Quantities tracked; **value** not posted to a GL asset account. |
| Fixed assets | `Asset` computes straight-line depreciation on the fly | Depreciation is **not** in the P&L (`net_profit` = revenue − COGS − expenses only). |
| Structure | `analytics/services.py` recomputes KPIs from raw rows | No trial balance, no balance sheet, nothing that must *balance*. |

**Key architectural fact:** the app deliberately has "no GL, no journals, just registers." Moving to a
GL is therefore additive-then-authoritative: we introduce a ledger, make domain events post to it,
and gradually make the ledger — not the ad-hoc aggregates — the source of truth for financial reports.

---

## 2. Target architecture

Introduce a new Django app: **`apps/ledger`**. It owns the double-entry core and becomes the single
source of truth for all financial statements. Domain apps (sales, finance, inventory, production,
processed_materials) keep their operational models but **emit journal entries** on the events that
have accounting meaning.

```
Domain event  ──►  Posting service  ──►  JournalEntry (balanced)  ──►  Ledger accounts
(Sale saved)       (sales.posting)       Dr/Cr lines                   Trial balance
                                                                       P&L / Balance sheet
```

### 2.1 New models (`apps/ledger/models.py`)

- **`Account`** — the chart of accounts node.
  - `code` (e.g. `1000`), `name`, `type` (ASSET / LIABILITY / EQUITY / INCOME / EXPENSE),
    `subtype` (e.g. current_asset, cogs, operating_expense), `normal_balance` (debit/credit,
    derivable from type), `parent` (self-FK for roll-ups/subtotals), `is_active`, `is_postable`
    (leaf accounts only), `currency`.
- **`FiscalYear`** / **`AccountingPeriod`** — period with `status` (open / closed / locked).
  Posting into a closed period is rejected. Enables period close and prevents back-dated tampering.
- **`JournalEntry`** — the header.
  - `date` (the *accounting* date — when the event is recognized, **not** created_at),
    `period` (FK), `memo`, `source_type` + `source_id` (generic link back to the Sale/Expense/etc.
    that produced it — idempotency key), `status` (draft / posted / reversed), `reversed_by`,
    `created_by`.
- **`JournalLine`** — the legs.
  - `entry` (FK), `account` (FK), `debit` (Decimal ≥ 0), `credit` (Decimal ≥ 0),
    `amount`/`memo`, optional dimensions: `wallet`, `product`, `supplier`, `customer`, `cost_center`.
  - Constraint: exactly one of debit/credit is non-zero.
- **Invariant (enforced in a service + a `CheckConstraint`/validation):** `Σ debit = Σ credit`
  per entry. Nothing posts unbalanced.

### 2.2 Posting services (one per domain app)

`apps/<domain>/posting.py`, each exposing `post_<event>(instance)` and `reverse_<event>(instance)`.
Called from model `save()`/signals or (preferred) from the existing service layer where the domain
mutation already happens transactionally. Every post is:

- **Idempotent** — keyed on `(source_type, source_id, event)`; re-running never double-posts.
- **Reversible** — edits/deletes post a reversing entry rather than mutating history (append-only GL).
- **Transactional** — the journal entry and the domain change commit together (`transaction.atomic`).

---

## 3. Chart of accounts (starter, tailored to this business)

A manufacturing/retail food business. Codes are conventional (1xxx assets … 5xxx expenses).

```
ASSETS (1000–1999)
  1000  Cash & wallets            ← one sub-account per Wallet (cash drawer, MoMo, bank)
  1100  Accounts Receivable       ← Invoices / credit Sales
  1200  Inventory – Raw materials
  1210  Inventory – Processed materials (WIP)
  1220  Inventory – Finished goods
  1300  Prepaid expenses
  1500  Fixed assets – cost       ← per Asset (or per category)
  1590  Accumulated depreciation  (contra-asset)

LIABILITIES (2000–2999)
  2000  Accounts Payable          ← supplier bills (Expenses on credit)
  2100  Accrued expenses
  2200  Deferred revenue          ← customer deposits / prepaid orders
  2300  Taxes payable (VAT/sales) ← if/when tax is tracked

EQUITY (3000–3999)
  3000  Owner's capital
  3100  Retained earnings
  3900  Owner's drawings

INCOME (4000–4999)
  4000  Sales revenue
  4100  Other income              ← income Transactions
  4900  Sales discounts (contra)

EXPENSES (5000–5999)
  5000  COGS                      ← matched at sale
  5100  Materials waste / spoilage
  5200  Operating expenses        ← sub-accounts per ExpenseCategory
  5300  Depreciation expense
```

`Wallet`, `Asset`, and `ExpenseCategory` map to (or auto-create) sub-accounts so existing screens
keep working while everything rolls into the GL. `Sale.payment_method` and `Expense.payment_method`
choose which cash sub-account (or AR/AP) a leg hits.

---

## 4. Posting rules (event → journal entries)

This is the heart of the migration. Each domain event becomes a balanced entry.

**Cash sale** (payment received now):
```
Dr Cash/Wallet (1000.x)      total
   Cr Sales revenue (4000)        subtotal
   Cr (Dr) Discounts (4900)       discount
Dr COGS (5000)               cost_of_goods
   Cr Inventory – Finished (1220) cost_of_goods
```

**Credit sale** (`payment_method="credit"`) — *this is the core bug the migration fixes*:
```
Dr Accounts Receivable (1100)  total     ← NOT cash
   Cr Sales revenue (4000)         subtotal
Dr COGS (5000) / Cr Inventory       cost_of_goods
```
Later, when paid: `Dr Cash/Wallet · Cr Accounts Receivable`. The `Invoice` model becomes the AR
document; `Invoice.amount_paid` drives the settlement entry.

**Expense paid in cash:** `Dr Operating expense (5200.x) · Cr Cash/Wallet`.
**Expense on credit (supplier bill):** `Dr Expense · Cr Accounts Payable`; on payment
`Dr AP · Cr Cash`. (Requires a new "bill vs. paid" flag on `Expense`, or a small `Bill` model.)

**Manual Transaction (income):** `Dr Cash · Cr Other income (4100)`.
**Manual Transaction (expense):** `Dr Expense · Cr Cash`.
**Wallet transfer:** `Dr Cash(dest) · Cr Cash(source)` — the two `WalletEntry` rows collapse to one entry.
**Wallet deposit/withdrawal (external):** `Dr/Cr Cash · Cr/Dr Owner's capital or Drawings` (needs a
reason so we know the contra account).

**Raw material purchase** (`StockMovement.reason=purchase`):
`Dr Inventory – Raw (1200) · Cr Cash/AP`.
**Processed material batch** (`ProcessedMaterialBatch`):
`Dr Inventory – Processed (1210) · Cr Inventory – Raw (1200)` (value of consumed raws).
**Production run** (`ProductionRun` completed):
`Dr Inventory – Finished (1220) · Cr Inventory – Raw/Processed` for the run `cost`.
**Waste / spoilage** (`reason=waste`): `Dr Materials waste (5100) · Cr Inventory`.
**Stock adjustment:** `Dr/Cr Inventory · Cr/Dr Inventory adjustment expense`.

**Asset purchase:** `Dr Fixed assets (1500) · Cr Cash/AP` (replaces booking the whole thing as an
expense). **Monthly depreciation** (new scheduled job): `Dr Depreciation expense (5300) · Cr
Accumulated depreciation (1590)`. **Disposal:** derecognize cost + accumulated depreciation, book
gain/loss.

> Note: COGS/inventory posting is already conceptually present (cost snapshots) — that makes the
> inventory legs mostly a matter of *valuing* movements that are already quantity-tracked.

---

## 5. The hard problems (call these out up front)

1. **Inventory valuation method.** Costs today are "latest value" (production_cost / unit_cost),
   not layered. A perpetual GL needs a consistent method — **weighted-average** is the least
   disruptive fit here. Decide and document; it affects every inventory leg and COGS.
2. **Historical backfill.** Two options:
   - **(A) Opening-balances only (recommended):** pick a cutover date, compute balances as of that
     date (cash per wallet, AR from open invoices, inventory value, asset carrying values), post one
     **opening journal entry** against Owner's capital / Retained earnings, and only post GL entries
     for events *after* cutover. Simple, safe, auditable.
   - **(B) Full replay:** re-post every historical Sale/Expense/etc. into the GL. Gives full history
     but is risky (data quality, changed costs, deleted rows) and slow. Only if tax/audit demands it.
3. **Credit-sale cleanup.** Existing credit sales that inflated wallets must be reclassified to AR at
   cutover so opening cash is real. This is a data-quality pass, not just code.
4. **`Wallet.current_balance` becomes derived from the GL**, not from summing domain rows — otherwise
   the two disagree. Plan to switch it to read cash-account balances once posting is live and reconciled.
5. **Period close & immutability.** Once a month is closed, entries are locked; corrections go to the
   next open period. Needs the `AccountingPeriod` gate and append-only (reversal) discipline.
6. **Tax handling.** If VAT/sales tax matters for reporting, model it now (tax on sales → Taxes
   payable) rather than retrofitting. Confirm the jurisdiction's requirement (RW EBM/VAT?).

---

## 6. Reporting (what the ledger unlocks)

Replace/supplement `analytics/services.py` with ledger-driven statements:

- **Trial balance** — Σ debits = Σ credits across all accounts for a period (the correctness check).
- **Income statement (accrual P&L)** — income − COGS − operating − depreciation, by period.
  Now includes depreciation and excludes uncollected-but-not-earned cash.
- **Balance sheet** — assets = liabilities + equity at a date. New capability.
- **AR/AP aging** — open receivables/payables bucketed by age.
- **Cash flow** — still available (cash accounts are just GL accounts), so you keep the cash view *and*
  gain accrual. Existing dashboard KPIs get recomputed from the GL so cash and accrual reconcile.

---

## 7. Phased rollout

Each phase is shippable and reversible; the GL runs in **shadow mode** (posting + reconciling but not
yet authoritative) until Phase 5.

- **Phase 0 — Design & sign-off.** Finalize chart of accounts, inventory valuation method, cutover
  date, backfill option (A vs B), tax scope. Output: this doc, ratified. *No code.*
- **Phase 1 — Ledger core.** `apps/ledger`: Account, FiscalYear/Period, JournalEntry/Line, the
  balancing invariant, a posting API (`post_entry(date, lines, source)`), admin, and thorough unit
  tests (balanced-only, idempotency, reversal, period lock). Seed the chart of accounts via migration.
- **Phase 2 — Opening balances.** Management command to compute and post cutover opening balances
  (cash, AR from open invoices, inventory value, assets, accumulated depreciation → equity). Reconcile
  against current dashboard. This is where credit-sale cleanup happens.
- **Phase 3 — Post live events (shadow).** Add `posting.py` to sales, finance, inventory, production,
  processed_materials. Wire into existing service/transaction boundaries. Every new event posts to the
  GL, but reports still read the old aggregates. Add a nightly **reconciliation job** that asserts
  GL-derived totals match the legacy aggregates; alert on drift.
- **Phase 4 — Accrual features.** *Partly done:* supplier bills / AP (Expense `on_credit`/`settled_at`
  → A/P + settlement), AR settlement from `Invoice.amount_paid`, monthly depreciation job
  (`post_depreciation`), and a period-close action are implemented. *Still open:* prepaid & accrued
  expense workflow, deferred revenue for deposits, and asset-purchase capitalisation.
- **Phase 5 — Cut over reporting.** Point trial balance, P&L, balance sheet, and dashboard KPIs at the
  GL. Switch `Wallet.current_balance` to read its cash account. Retire/redirect the legacy aggregate
  paths once reconciliation has been green for a full period.
- **Phase 6 — Frontend.** *Done:* Ledger/Chart-of-accounts screens, trial balance, accrual P&L and
  balance sheet, journal drill-down, a Periods tab (close/reopen) and a manual balanced-entry modal.
  *Still open:* AR/AP aging views and per-Sale/Expense journal links. (Remember: frontend serves
  **compiled JS** — recompile with `tsc -b --force` after editing `.tsx`; the accrual sandbox image
  rebuilds from source via `tsc -b && vite build`.)

---

## 8. Testing & safety

- **Backend tests run in Docker:** `docker exec adminator-scratch-backend python -m pytest`
  (no local venv; API under `/api/v1/`).
- Golden-rule tests: no entry posts unbalanced; every domain event has a matching GL entry;
  edit/delete produces a reversal, never a mutation; closed periods reject posts.
- **Reconciliation harness** (Phase 3) is the real safety net: GL must agree with the legacy numbers
  every night before we trust it.
- Keep the legacy aggregates alive and comparable through Phase 5 so you can roll back instantly.

---

## 9. Open decisions (need your input before Phase 1)

1. **Inventory valuation:** weighted-average (recommended) vs FIFO vs latest-cost?
2. **Backfill:** opening-balances-only at a cutover date (recommended) vs full historical replay?
3. **Cutover date:** start of current month? Start of fiscal year?
4. **Tax:** does VAT / sales tax need to be in the ledger now, or out of scope for v1?
5. **AP scope:** do you actually buy on credit from suppliers, or is everything paid on the spot
   (which would let us defer the AP machinery)?
6. **Multi-currency:** single currency (RWF) assumed — confirm.
```
