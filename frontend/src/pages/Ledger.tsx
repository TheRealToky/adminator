import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen, Scale, TrendingUp, Landmark, ListTree, CheckCircle2, AlertTriangle,
  CalendarClock, Plus, Lock, LockOpen, Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { ledger } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Modal } from '@/components/ui/Modal';
import { formatMoney, formatDate } from '@/lib/format';
import type {
  AccountingPeriod, BalanceSheet, IncomeStatement, JournalEntry, LedgerAccount,
  ManualJournalLineInput, StatementLine, TrialBalance, TrialBalanceLine,
} from '@/api/types';

type Tab = 'trial-balance' | 'income-statement' | 'balance-sheet' | 'accounts' | 'journal' | 'periods';

const todayISO = () => new Date().toISOString().slice(0, 10);
const monthStartISO = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};

export function LedgerPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('trial-balance');

  const tabs: Array<{ key: Tab; icon: typeof Scale }> = [
    { key: 'trial-balance', icon: Scale },
    { key: 'income-statement', icon: TrendingUp },
    { key: 'balance-sheet', icon: Landmark },
    { key: 'accounts', icon: ListTree },
    { key: 'journal', icon: BookOpen },
    { key: 'periods', icon: CalendarClock },
  ];

  return (
    <>
      <PageHeader title={t('ledger.title')} subtitle={t('ledger.subtitle')} />
      <div className="card">
        <div className="card-header">
          <div className="flex gap-1 flex-wrap">
            {tabs.map(({ key, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium inline-flex items-center gap-1.5 ${
                  tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Icon size={15} />
                {t(`ledger.tabs.${key}`)}
              </button>
            ))}
          </div>
        </div>
        {tab === 'trial-balance' && <TrialBalanceTab />}
        {tab === 'income-statement' && <IncomeStatementTab />}
        {tab === 'balance-sheet' && <BalanceSheetTab />}
        {tab === 'accounts' && <AccountsTab />}
        {tab === 'journal' && <JournalTab />}
        {tab === 'periods' && <PeriodsTab />}
      </div>
    </>
  );
}

// ── Shared bits ─────────────────────────────────────────────────────────────
function BalancedBadge({ balanced }: { balanced: boolean }) {
  const { t } = useTranslation();
  return balanced ? (
    <span className="badge-green inline-flex items-center gap-1">
      <CheckCircle2 size={13} /> {t('ledger.balanced')}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 text-red-700 px-2 py-0.5 text-xs font-medium">
      <AlertTriangle size={13} /> {t('ledger.notBalanced')}
    </span>
  );
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="date" className="input" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function TotalRow({ label, amount, strong }: { label: string; amount: string; strong?: boolean }) {
  return (
    <div className={`flex items-center justify-between px-4 py-2 ${strong ? 'font-semibold text-slate-900' : 'text-slate-600'}`}>
      <span>{label}</span>
      <span className="tabular-nums">{formatMoney(amount)}</span>
    </div>
  );
}

function StatementSection({ title, rows, total, totalLabel }: {
  title: string; rows: StatementLine[]; total: string; totalLabel: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <div className="divide-y divide-slate-100">
        {rows.length === 0 ? (
          <div className="px-4 py-3 text-sm text-slate-400">—</div>
        ) : rows.map((r) => (
          <div key={r.account_code} className="flex items-center justify-between px-4 py-2 text-sm">
            <span className="text-slate-700"><span className="text-slate-400 mr-2 tabular-nums">{r.account_code}</span>{r.account_name}</span>
            <span className="tabular-nums text-slate-900">{formatMoney(r.amount)}</span>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-200 bg-slate-50">
        <TotalRow label={totalLabel} amount={total} strong />
      </div>
    </div>
  );
}

// ── Trial balance ────────────────────────────────────────────────────────────
function TrialBalanceTab() {
  const { t } = useTranslation();
  const [asOf, setAsOf] = useState(todayISO());
  const q = useQuery({ queryKey: ['tb', asOf], queryFn: () => ledger.reports.trialBalance({ as_of: asOf }) });
  const data = q.data as TrialBalance | undefined;

  const columns: Column<TrialBalanceLine>[] = [
    { key: 'code', header: t('ledger.cols.code'), render: (r) => <span className="tabular-nums text-slate-500">{r.account_code}</span> },
    { key: 'name', header: t('ledger.cols.account'), render: (r) => <span className="font-medium">{r.account_name}</span> },
    { key: 'type', header: t('ledger.cols.type'), render: (r) => <span className="badge-gray capitalize">{r.type}</span> },
    { key: 'debit', header: t('ledger.cols.debit'), align: 'right', render: (r) => <span className="tabular-nums">{Number(r.debit) ? formatMoney(r.debit) : '—'}</span> },
    { key: 'credit', header: t('ledger.cols.credit'), align: 'right', render: (r) => <span className="tabular-nums">{Number(r.credit) ? formatMoney(r.credit) : '—'}</span> },
  ];

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <DateField label={t('ledger.asOf')} value={asOf} onChange={setAsOf} />
        {data && <BalancedBadge balanced={data.balanced} />}
      </div>
      <DataTable columns={columns} data={data?.lines} loading={q.isLoading} rowKey={(r) => r.account_code} />
      {data && (
        <div className="rounded-lg border border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between px-4 py-2 font-semibold text-slate-900">
            <span>{t('ledger.totals')}</span>
            <span className="flex gap-8 tabular-nums">
              <span>{formatMoney(data.total_debit)}</span>
              <span>{formatMoney(data.total_credit)}</span>
            </span>
          </div>
          {Number(data.difference) !== 0 && (
            <div className="px-4 py-2 text-sm text-red-700">{t('ledger.difference')}: {formatMoney(data.difference)}</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Income statement ─────────────────────────────────────────────────────────
function IncomeStatementTab() {
  const { t } = useTranslation();
  const [start, setStart] = useState(monthStartISO());
  const [end, setEnd] = useState(todayISO());
  const q = useQuery({ queryKey: ['is', start, end], queryFn: () => ledger.reports.incomeStatement({ start, end }) });
  const data = q.data as IncomeStatement | undefined;

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-end gap-3 flex-wrap">
        <DateField label={t('ledger.from')} value={start} onChange={setStart} />
        <DateField label={t('ledger.to')} value={end} onChange={setEnd} />
      </div>
      {q.isLoading || !data ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('common.loading')}</div>
      ) : (
        <div className="space-y-4 max-w-2xl">
          <StatementSection title={t('ledger.income')} rows={data.income} total={data.total_income} totalLabel={t('ledger.totalIncome')} />
          <div className="rounded-lg border border-slate-200 bg-slate-50">
            <TotalRow label={t('ledger.cogs')} amount={data.cost_of_goods_sold} />
            <div className="border-t border-slate-200"><TotalRow label={t('ledger.grossProfit')} amount={data.gross_profit} strong /></div>
          </div>
          <StatementSection title={t('ledger.expenses')} rows={data.expenses} total={data.total_expenses} totalLabel={t('ledger.totalExpenses')} />
          <div className={`rounded-lg border-2 ${Number(data.net_profit) >= 0 ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
            <div className="flex items-center justify-between px-4 py-3 font-bold text-slate-900">
              <span>{t('ledger.netProfit')}</span>
              <span className="tabular-nums">{formatMoney(data.net_profit)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Balance sheet ────────────────────────────────────────────────────────────
function BalanceSheetTab() {
  const { t } = useTranslation();
  const [asOf, setAsOf] = useState(todayISO());
  const q = useQuery({ queryKey: ['bs', asOf], queryFn: () => ledger.reports.balanceSheet({ as_of: asOf }) });
  const data = q.data as BalanceSheet | undefined;

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <DateField label={t('ledger.asOf')} value={asOf} onChange={setAsOf} />
        {data && <BalancedBadge balanced={data.balanced} />}
      </div>
      {q.isLoading || !data ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('common.loading')}</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          <StatementSection title={t('ledger.assets')} rows={data.assets} total={data.total_assets} totalLabel={t('ledger.totalAssets')} />
          <div className="space-y-4">
            <StatementSection title={t('ledger.liabilities')} rows={data.liabilities} total={data.total_liabilities} totalLabel={t('ledger.totalLiabilities')} />
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t('ledger.equity')}</div>
              <div className="divide-y divide-slate-100">
                {data.equity.map((r) => (
                  <div key={r.account_code} className="flex items-center justify-between px-4 py-2 text-sm">
                    <span className="text-slate-700"><span className="text-slate-400 mr-2 tabular-nums">{r.account_code}</span>{r.account_name}</span>
                    <span className="tabular-nums">{formatMoney(r.amount)}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between px-4 py-2 text-sm text-slate-600">
                  <span>{t('ledger.currentEarnings')}</span>
                  <span className="tabular-nums">{formatMoney(data.current_year_earnings)}</span>
                </div>
              </div>
              <div className="border-t border-slate-200 bg-slate-50"><TotalRow label={t('ledger.totalEquity')} amount={data.total_equity} strong /></div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50"><TotalRow label={t('ledger.totalLiabEquity')} amount={data.total_liabilities_and_equity} strong /></div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Chart of accounts ────────────────────────────────────────────────────────
function AccountsTab() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ['coa'], queryFn: () => ledger.accounts.list({ page_size: 500, ordering: 'code' }) });

  const columns: Column<LedgerAccount>[] = [
    { key: 'code', header: t('ledger.cols.code'), render: (r) => <span className="tabular-nums text-slate-500">{r.code}</span> },
    { key: 'name', header: t('ledger.cols.account'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'type', header: t('ledger.cols.type'), render: (r) => <span className="badge-gray capitalize">{r.type_display}</span> },
    { key: 'normal', header: t('ledger.cols.normal'), render: (r) => <span className="capitalize text-slate-600">{r.normal_balance}</span> },
    { key: 'postable', header: t('ledger.cols.postable'), align: 'right', render: (r) => (
      r.is_postable ? <span className="badge-green">{t('common.yes')}</span> : <span className="badge-gray">{t('common.no')}</span>
    ) },
  ];

  return (
    <div className="p-5">
      <DataTable columns={columns} data={q.data?.results} loading={q.isLoading} rowKey={(r) => r.id} />
    </div>
  );
}

// ── Journal ──────────────────────────────────────────────────────────────────
function JournalTab() {
  const { t } = useTranslation();
  const [showNew, setShowNew] = useState(false);
  const q = useQuery({ queryKey: ['journal'], queryFn: () => ledger.journalEntries.list({ page_size: 25, ordering: '-date' }) });
  const entries = (q.data?.results ?? []) as JournalEntry[];

  return (
    <div className="p-5 space-y-3">
      <div className="flex justify-end">
        <button onClick={() => setShowNew(true)} className="btn-primary inline-flex items-center gap-1.5">
          <Plus size={15} /> {t('ledger.newEntry')}
        </button>
      </div>
      {showNew && <ManualEntryModal onClose={() => setShowNew(false)} />}
      {q.isLoading ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('common.loading')}</div>
      ) : entries.length === 0 ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('ledger.noEntries')}</div>
      ) : entries.map((e) => (
        <div key={e.id} className="rounded-lg border border-slate-200 overflow-hidden">
          <div className="flex items-center justify-between gap-2 bg-slate-50 px-4 py-2 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium text-slate-900">{formatDate(e.date)}</span>
              <span className="text-slate-500">{e.memo || e.event}</span>
              {e.status === 'reversed' && <span className="badge-gray">{t('ledger.reversed')}</span>}
              {e.is_system && <span className="badge-gray">{t('ledger.system')}</span>}
            </div>
            <span className="text-xs text-slate-400 tabular-nums">{e.source_type}</span>
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-100">
              {e.lines.map((l) => (
                <tr key={l.id}>
                  <td className="px-4 py-1.5 text-slate-400 tabular-nums w-24">{l.account_code}</td>
                  <td className="px-2 py-1.5 text-slate-700">{l.account_name}</td>
                  <td className="px-4 py-1.5 text-right tabular-nums text-slate-900 w-32">{Number(l.debit) ? formatMoney(l.debit) : ''}</td>
                  <td className="px-4 py-1.5 text-right tabular-nums text-slate-900 w-32">{Number(l.credit) ? formatMoney(l.credit) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

// ── Manual journal entry ─────────────────────────────────────────────────────
type DraftLine = { account: string; debit: string; credit: string };
const blankLine = (): DraftLine => ({ account: '', debit: '', credit: '' });

function ManualEntryModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [date, setDate] = useState(todayISO());
  const [memo, setMemo] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([blankLine(), blankLine()]);

  const accountsQ = useQuery({
    queryKey: ['coa', 'postable'],
    queryFn: () => ledger.accounts.list({ page_size: 500, ordering: 'code', is_postable: true }),
  });
  const accounts = (accountsQ.data?.results ?? []) as LedgerAccount[];

  const totals = useMemo(() => {
    const debit = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
    const credit = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
    return { debit, credit, balanced: debit === credit && debit > 0 };
  }, [lines]);

  const setLine = (i: number, patch: Partial<DraftLine>) =>
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        date, memo,
        lines: lines
          .filter((l) => l.account && (Number(l.debit) || Number(l.credit)))
          .map<ManualJournalLineInput>((l) => ({
            account: l.account,
            ...(Number(l.debit) ? { debit: l.debit } : { credit: l.credit }),
          })),
      };
      return ledger.journalEntries.createManual(payload);
    },
    onSuccess: () => {
      toast.success(t('ledger.entryPosted'));
      qc.invalidateQueries({ queryKey: ['journal'] });
      qc.invalidateQueries({ queryKey: ['tb'] });
      qc.invalidateQueries({ queryKey: ['bs'] });
      onClose();
    },
    onError: (err) => toast.error(extractErrorMessage(err, t('ledger.entryFailed'))),
  });

  return (
    <Modal
      open onClose={onClose} title={t('ledger.newEntry')} size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button className="btn-primary" disabled={!totals.balanced || save.isPending} onClick={() => save.mutate()}>
            {t('ledger.postEntry')}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">{t('ledger.date')}</label>
            <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label className="label">{t('ledger.memo')}</label>
            <input className="input" value={memo} onChange={(e) => setMemo(e.target.value)} placeholder={t('ledger.memoPlaceholder')} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="text-left px-3 py-2 font-semibold">{t('ledger.cols.account')}</th>
                <th className="text-right px-3 py-2 font-semibold w-32">{t('ledger.cols.debit')}</th>
                <th className="text-right px-3 py-2 font-semibold w-32">{t('ledger.cols.credit')}</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lines.map((l, i) => (
                <tr key={i}>
                  <td className="px-3 py-1.5">
                    <select className="input" value={l.account} onChange={(e) => setLine(i, { account: e.target.value })}>
                      <option value="">—</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>{a.code} · {a.name}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-1.5">
                    <input type="number" min="0" step="0.01" className="input text-right tabular-nums" value={l.debit}
                      onChange={(e) => setLine(i, { debit: e.target.value, credit: '' })} />
                  </td>
                  <td className="px-3 py-1.5">
                    <input type="number" min="0" step="0.01" className="input text-right tabular-nums" value={l.credit}
                      onChange={(e) => setLine(i, { credit: e.target.value, debit: '' })} />
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    {lines.length > 2 && (
                      <button className="btn-ghost p-1 text-red-600" onClick={() => setLines((p) => p.filter((_, idx) => idx !== i))}>
                        <Trash2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50 border-t border-slate-200">
              <tr className="text-sm font-semibold text-slate-900">
                <td className="px-3 py-2 text-right">{t('ledger.totals')}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatMoney(String(totals.debit))}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatMoney(String(totals.credit))}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <button className="btn-ghost inline-flex items-center gap-1.5 text-brand-700" onClick={() => setLines((p) => [...p, blankLine()])}>
            <Plus size={14} /> {t('ledger.addLine')}
          </button>
          {totals.balanced
            ? <BalancedBadge balanced />
            : <span className="text-xs text-amber-600">{t('ledger.mustBalance')}</span>}
        </div>
      </div>
    </Modal>
  );
}

// ── Periods ──────────────────────────────────────────────────────────────────
function PeriodsTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['periods'], queryFn: () => ledger.periods.list({ page_size: 100, ordering: '-start_date' }) });
  const periods = (q.data?.results ?? []) as AccountingPeriod[];

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['periods'] });
    qc.invalidateQueries({ queryKey: ['journal'] });
  };
  const close = useMutation({
    mutationFn: (id: string) => ledger.periods.close(id),
    onSuccess: () => { toast.success(t('ledger.periodClosed')); invalidate(); },
    onError: (err) => toast.error(extractErrorMessage(err, t('common.error'))),
  });
  const reopen = useMutation({
    mutationFn: (id: string) => ledger.periods.reopen(id),
    onSuccess: () => { toast.success(t('ledger.periodReopened')); invalidate(); },
    onError: (err) => toast.error(extractErrorMessage(err, t('common.error'))),
  });

  const statusClass: Record<string, string> = {
    open: 'badge-green', closed: 'badge-yellow', locked: 'badge-gray',
  };

  return (
    <div className="p-5 space-y-3">
      {q.isLoading ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('common.loading')}</div>
      ) : periods.length === 0 ? (
        <div className="text-sm text-slate-400 py-8 text-center">{t('ledger.noPeriods')}</div>
      ) : (
        <div className="rounded-lg border border-slate-200 overflow-hidden divide-y divide-slate-100">
          {periods.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <span className="font-medium text-slate-900 tabular-nums">{p.label}</span>
                <span className={`${statusClass[p.status] ?? 'badge-gray'} capitalize`}>{t(`ledger.periodStatus.${p.status}`)}</span>
              </div>
              <div className="flex items-center gap-2">
                {p.status === 'open' ? (
                  <button className="btn-secondary inline-flex items-center gap-1.5" disabled={close.isPending} onClick={() => close.mutate(p.id)}>
                    <Lock size={14} /> {t('ledger.closePeriod')}
                  </button>
                ) : p.status === 'closed' ? (
                  <button className="btn-ghost inline-flex items-center gap-1.5" disabled={reopen.isPending} onClick={() => reopen.mutate(p.id)}>
                    <LockOpen size={14} /> {t('ledger.reopenPeriod')}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
