import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Pencil, Trash2, Wallet as WalletIcon,
  ArrowDownToLine, ArrowUpFromLine, ArrowLeftRight, History,
} from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { finance } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
import type { Wallet, WalletAccountType, WalletLedgerItem } from '@/api/types';

const ACCOUNT_TYPE_KEYS: WalletAccountType[] = [
  'cash',
  'mobile_money',
  'bank',
  'card',
  'other',
];

const today = () => new Date().toISOString().slice(0, 10);

const emptyForm: Partial<Wallet> = {
  name: '',
  account_type: 'cash',
  opening_balance: '0',
  institution: '',
  account_number: '',
  is_active: true,
  notes: '',
};

type MovementState = {
  open: boolean;
  mode: 'deposit' | 'withdraw';
  wallet: Wallet | null;
};

type MovementForm = {
  amount: string;
  occurred_on: string;
  description: string;
  reference: string;
};

type TransferForm = MovementForm & { destination: string };

const emptyMovement: MovementForm = {
  amount: '0',
  occurred_on: today(),
  description: '',
  reference: '',
};

export function WalletsPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Wallet>({
    queryKey: ['wallets'],
    fetcher: (p) => finance.wallets.list(p),
    deleter: (id) => finance.wallets.remove(id),
  });

  // All wallets (unpaginated) — powers the totals header and transfer targets.
  const allWallets = useQuery({
    queryKey: ['wallets-all'],
    queryFn: () => finance.wallets.list({ page_size: 200 }),
  });

  const wallets = allWallets.data?.results ?? [];
  const activeWallets = wallets.filter((w) => w.is_active);
  const totalHoldings = activeWallets.reduce(
    (sum, w) => sum + Number(w.current_balance),
    0,
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Wallet | null>(null);
  const [form, setForm] = useState<Partial<Wallet>>(emptyForm);
  const [toDelete, setToDelete] = useState<Wallet | null>(null);

  const [movement, setMovement] = useState<MovementState>({
    open: false, mode: 'deposit', wallet: null,
  });
  const [movementForm, setMovementForm] = useState<MovementForm>(emptyMovement);

  const [transfer, setTransfer] = useState<{ open: boolean; wallet: Wallet | null }>({
    open: false, wallet: null,
  });
  const [transferForm, setTransferForm] = useState<TransferForm>({
    ...emptyMovement, destination: '',
  });

  const [entriesFor, setEntriesFor] = useState<Wallet | null>(null);

  function invalidateAll() {
    qc.invalidateQueries({ queryKey: ['wallets'] });
    qc.invalidateQueries({ queryKey: ['wallets-all'] });
    qc.invalidateQueries({ queryKey: ['wallet-entries'] });
  }

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.wallets.update(editing.id, form) : finance.wallets.create(form),
    onSuccess: () => {
      toast.success(editing ? t('wallets.updated') : t('wallets.created'));
      invalidateAll();
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const recordMovement = useMutation({
    mutationFn: () => {
      const w = movement.wallet!;
      const payload = {
        amount: Number(movementForm.amount),
        occurred_on: movementForm.occurred_on || undefined,
        description: movementForm.description || undefined,
        reference: movementForm.reference || undefined,
      };
      return movement.mode === 'deposit'
        ? finance.wallets.deposit(w.id, payload)
        : finance.wallets.withdraw(w.id, payload);
    },
    onSuccess: () => {
      toast.success(
        movement.mode === 'deposit' ? t('wallets.deposited') : t('wallets.withdrew'),
      );
      invalidateAll();
      setMovement((m) => ({ ...m, open: false }));
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const recordTransfer = useMutation({
    mutationFn: () =>
      finance.wallets.transfer(transfer.wallet!.id, {
        destination: transferForm.destination,
        amount: Number(transferForm.amount),
        occurred_on: transferForm.occurred_on || undefined,
        description: transferForm.description || undefined,
        reference: transferForm.reference || undefined,
      }),
    onSuccess: () => {
      toast.success(t('wallets.transferred'));
      invalidateAll();
      setTransfer((s) => ({ ...s, open: false }));
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  }
  function openEdit(row: Wallet) {
    setEditing(row);
    setForm({
      name: row.name,
      account_type: row.account_type,
      opening_balance: row.opening_balance,
      institution: row.institution,
      account_number: row.account_number,
      is_active: row.is_active,
      notes: row.notes,
    });
    setOpen(true);
  }
  function openMovement(wallet: Wallet, mode: 'deposit' | 'withdraw') {
    setMovement({ open: true, mode, wallet });
    setMovementForm({ ...emptyMovement });
  }
  function openTransfer(wallet: Wallet) {
    setTransfer({ open: true, wallet });
    setTransferForm({ ...emptyMovement, destination: '' });
  }

  const columns: Column<Wallet>[] = [
    {
      key: 'name',
      header: t('wallets.columns.name'),
      render: (r) => (
        <div>
          <div className="font-medium">{r.name}</div>
          {(r.institution || r.account_number) && (
            <div className="text-xs text-slate-500">
              {[r.institution, r.account_number].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'type',
      header: t('wallets.columns.type'),
      render: (r) => (
        <span className="badge-gray">{t(`wallets.accountTypes.${r.account_type}`)}</span>
      ),
    },
    {
      key: 'opening',
      header: t('wallets.columns.opening'),
      align: 'right',
      render: (r) => formatMoney(r.opening_balance),
    },
    {
      key: 'balance',
      header: t('wallets.columns.balance'),
      align: 'right',
      render: (r) => (
        <span
          className={`font-semibold ${
            Number(r.current_balance) < 0 ? 'text-red-600' : 'text-slate-900'
          }`}
        >
          {formatMoney(r.current_balance)}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('wallets.columns.status'),
      render: (r) =>
        r.is_active ? (
          <span className="badge-green">{t('common.active')}</span>
        ) : (
          <span className="badge-gray">{t('common.off')}</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <div className="flex justify-end gap-1">
          <button
            className="btn-ghost p-1.5 text-emerald-600"
            title={t('wallets.actions.deposit')}
            onClick={(e) => { e.stopPropagation(); openMovement(r, 'deposit'); }}
          >
            <ArrowDownToLine size={14} />
          </button>
          <button
            className="btn-ghost p-1.5 text-amber-600"
            title={t('wallets.actions.withdraw')}
            onClick={(e) => { e.stopPropagation(); openMovement(r, 'withdraw'); }}
          >
            <ArrowUpFromLine size={14} />
          </button>
          <button
            className="btn-ghost p-1.5"
            title={t('wallets.actions.transfer')}
            onClick={(e) => { e.stopPropagation(); openTransfer(r); }}
          >
            <ArrowLeftRight size={14} />
          </button>
          <button
            className="btn-ghost p-1.5"
            title={t('wallets.actions.history')}
            onClick={(e) => { e.stopPropagation(); setEntriesFor(r); }}
          >
            <History size={14} />
          </button>
          <button
            className="btn-ghost p-1.5"
            onClick={(e) => { e.stopPropagation(); openEdit(r); }}
          >
            <Pencil size={14} />
          </button>
          <button
            className="btn-ghost p-1.5 text-red-600"
            onClick={(e) => { e.stopPropagation(); setToDelete(r); }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  const exportColumns: ExportColumn<Wallet>[] = [
    { key: 'name', header: t('wallets.exportCols.name'), value: (r) => r.name },
    {
      key: 'account_type',
      header: t('wallets.exportCols.type'),
      value: (r) => t(`wallets.accountTypes.${r.account_type}`),
    },
    { key: 'institution', header: t('wallets.exportCols.institution'), value: (r) => r.institution },
    { key: 'account_number', header: t('wallets.exportCols.accountNumber'), value: (r) => r.account_number },
    { key: 'opening_balance', header: t('wallets.exportCols.opening'), value: (r) => Number(r.opening_balance) },
    { key: 'current_balance', header: t('wallets.exportCols.balance'), value: (r) => Number(r.current_balance) },
    {
      key: 'is_active',
      header: t('wallets.exportCols.active'),
      value: (r) => (r.is_active ? t('common.yes') : t('common.no')),
    },
    { key: 'notes', header: t('wallets.exportCols.notes'), value: (r) => r.notes },
  ];

  const transferTargets = wallets.filter(
    (w) => w.is_active && w.id !== transfer.wallet?.id,
  );

  return (
    <>
      <PageHeader
        title={t('wallets.title')}
        subtitle={t('wallets.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="wallets"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated((p) => finance.wallets.list(p))}
            />
            <button onClick={openCreate} className="btn-primary">
              <Plus size={16} /> {t('wallets.new')}
            </button>
          </>
        }
      />

      {/* Totals */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            {t('wallets.totals.holdings')}
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {formatMoney(totalHoldings)}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            {t('wallets.totals.activeAccounts')}
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {activeWallets.length}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            {t('wallets.totals.totalAccounts')}
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {wallets.length}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="p-3 border-b border-slate-200">
          <SearchBar
            value={list.search}
            onChange={list.setSearch}
            placeholder={t('wallets.searchPlaceholder')}
          />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={
            <EmptyState
              icon={WalletIcon}
              title={t('wallets.emptyTitle')}
              description={t('wallets.emptyDescription')}
            />
          }
        />
        {list.data && (
          <Pagination
            page={list.page}
            pageSize={list.pageSize}
            total={list.data.count}
            onChange={list.setPage}
          />
        )}
      </div>

      {/* Create / edit */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('wallets.editModal') : t('wallets.newModal')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </button>
            <button
              className="btn-primary"
              disabled={!form.name || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">{t('wallets.fields.name')}</label>
            <input
              className="input"
              value={form.name ?? ''}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('wallets.fields.namePlaceholder')}
            />
          </div>
          <div>
            <label className="label">{t('wallets.fields.accountType')}</label>
            <select
              className="input"
              value={form.account_type ?? 'cash'}
              onChange={(e) =>
                setForm({ ...form, account_type: e.target.value as WalletAccountType })
              }
            >
              {ACCOUNT_TYPE_KEYS.map((k) => (
                <option key={k} value={k}>{t(`wallets.accountTypes.${k}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">
              {t('wallets.fields.openingBalance')}
              {editing && (
                <span className="text-slate-400"> ({t('wallets.fields.openingLocked')})</span>
              )}
            </label>
            <input
              type="number"
              step="0.01"
              className="input"
              value={form.opening_balance ?? '0'}
              onChange={(e) => setForm({ ...form, opening_balance: e.target.value })}
            />
          </div>
          <div>
            <label className="label">
              {t('wallets.fields.institution')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <input
              className="input"
              value={form.institution ?? ''}
              onChange={(e) => setForm({ ...form, institution: e.target.value })}
              placeholder={t('wallets.fields.institutionPlaceholder')}
            />
          </div>
          <div>
            <label className="label">
              {t('wallets.fields.accountNumber')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <input
              className="input"
              value={form.account_number ?? ''}
              onChange={(e) => setForm({ ...form, account_number: e.target.value })}
              placeholder={t('wallets.fields.accountNumberPlaceholder')}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={form.is_active ?? true}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              {t('wallets.fields.isActive')}
            </label>
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('common.notes')}</label>
            <textarea
              className="input"
              rows={2}
              value={form.notes ?? ''}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
        </div>
      </Modal>

      {/* Deposit / withdraw */}
      <Modal
        open={movement.open}
        onClose={() => setMovement((m) => ({ ...m, open: false }))}
        title={
          movement.mode === 'deposit'
            ? t('wallets.movement.depositTitle', { name: movement.wallet?.name ?? '' })
            : t('wallets.movement.withdrawTitle', { name: movement.wallet?.name ?? '' })
        }
        footer={
          <>
            <button
              className="btn-secondary"
              onClick={() => setMovement((m) => ({ ...m, open: false }))}
            >
              {t('common.cancel')}
            </button>
            <button
              className="btn-primary"
              disabled={
                !movementForm.amount ||
                Number(movementForm.amount) <= 0 ||
                recordMovement.isPending
              }
              onClick={() => recordMovement.mutate()}
            >
              {recordMovement.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <MovementFields form={movementForm} setForm={setMovementForm} />
      </Modal>

      {/* Transfer */}
      <Modal
        open={transfer.open}
        onClose={() => setTransfer((s) => ({ ...s, open: false }))}
        title={t('wallets.transfer.title', { name: transfer.wallet?.name ?? '' })}
        footer={
          <>
            <button
              className="btn-secondary"
              onClick={() => setTransfer((s) => ({ ...s, open: false }))}
            >
              {t('common.cancel')}
            </button>
            <button
              className="btn-primary"
              disabled={
                !transferForm.destination ||
                !transferForm.amount ||
                Number(transferForm.amount) <= 0 ||
                recordTransfer.isPending
              }
              onClick={() => recordTransfer.mutate()}
            >
              {recordTransfer.isPending ? t('common.saving') : t('wallets.transfer.submit')}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">{t('wallets.transfer.destination')}</label>
            <select
              className="input"
              value={transferForm.destination}
              onChange={(e) => setTransferForm((f) => ({ ...f, destination: e.target.value }))}
            >
              <option value="">{t('common.select')}</option>
              {transferTargets.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} — {formatMoney(w.current_balance)}
                </option>
              ))}
            </select>
            {transferTargets.length === 0 && (
              <p className="text-xs text-slate-500 mt-1">{t('wallets.transfer.noTargets')}</p>
            )}
          </div>
          <MovementFields
            form={transferForm}
            setForm={(updater) => setTransferForm((f) => ({ ...f, ...updater(f) }))}
          />
        </div>
      </Modal>

      {/* Entries history */}
      <Modal
        open={!!entriesFor}
        onClose={() => setEntriesFor(null)}
        title={t('wallets.history.title', { name: entriesFor?.name ?? '' })}
        size="lg"
      >
        {entriesFor && <EntriesList walletId={entriesFor.id} />}
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('wallets.deleteTitle')}
        message={t('wallets.deleteMessage', { name: toDelete?.name ?? '' })}
        confirmLabel={t('common.delete')}
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (toDelete)
            list.deleteMutation.mutate(toDelete.id, {
              onSettled: () => {
                setToDelete(null);
                invalidateAll();
              },
            });
        }}
      />
    </>
  );
}

// ── Shared amount/date/description fields ───────────────────────────────────
function MovementFields({
  form,
  setForm,
}: {
  form: MovementForm;
  setForm: (updater: (f: MovementForm) => MovementForm) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label className="label">{t('wallets.movement.amount')}</label>
        <input
          type="number"
          step="0.01"
          min="0"
          className="input"
          value={form.amount}
          onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
        />
      </div>
      <div>
        <label className="label">{t('wallets.movement.date')}</label>
        <input
          type="date"
          className="input"
          value={form.occurred_on}
          onChange={(e) => setForm((f) => ({ ...f, occurred_on: e.target.value }))}
        />
      </div>
      <div className="sm:col-span-2">
        <label className="label">{t('wallets.movement.description')}</label>
        <input
          className="input"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
      </div>
      <div className="sm:col-span-2">
        <label className="label">{t('wallets.movement.reference')}</label>
        <input
          className="input"
          value={form.reference}
          onChange={(e) => setForm((f) => ({ ...f, reference: e.target.value }))}
        />
      </div>
    </div>
  );
}

// ── A wallet's unified activity: manual entries + linked flows ──────────────
const SOURCE_BADGE: Record<WalletLedgerItem['source'], string> = {
  manual: 'badge-gray',
  sale: 'badge-green',
  transaction: 'badge-blue',
  expense: 'badge-gray',
};

function EntriesList({ walletId }: { walletId: string }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ['wallet-ledger', walletId],
    queryFn: () => finance.wallets.ledger(walletId),
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500 py-6 text-center">{t('common.loading')}</p>;
  }
  const rows = query.data ?? [];
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500 py-6 text-center">{t('wallets.history.empty')}</p>;
  }

  return (
    <div className="max-h-[60vh] overflow-y-auto -mx-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-slate-400">
            <th className="py-2 px-1 font-semibold">{t('wallets.history.date')}</th>
            <th className="py-2 px-1 font-semibold">{t('wallets.history.type')}</th>
            <th className="py-2 px-1 font-semibold">{t('wallets.history.description')}</th>
            <th className="py-2 px-1 font-semibold text-right">{t('wallets.history.amount')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.source}:${r.id}`} className="border-t border-slate-100">
              <td className="py-2 px-1 whitespace-nowrap">{formatDate(r.occurred_on)}</td>
              <td className="py-2 px-1">
                <span className={SOURCE_BADGE[r.source]}>{r.kind_display}</span>
              </td>
              <td className="py-2 px-1">{r.description || '—'}</td>
              <td
                className={`py-2 px-1 text-right font-semibold ${
                  r.direction === 'in' ? 'text-emerald-600' : 'text-slate-900'
                }`}
              >
                {r.direction === 'in' ? '+' : '−'}{formatMoney(r.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
