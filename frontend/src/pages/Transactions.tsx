import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, ArrowLeftRight, Folder } from 'lucide-react';
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
import type { Transaction, TransactionCategory, TransactionDirection } from '@/api/types';

type Tab = 'transactions' | 'categories';

export function TransactionsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('transactions');
  return (
    <>
      <PageHeader title={t('transactions.title')} subtitle={t('transactions.subtitle')} />
      <div className="card">
        <div className="card-header">
          <div className="flex gap-1">
            {(['transactions', 'categories'] as Tab[]).map((tabKey) => (
              <button
                key={tabKey}
                onClick={() => setTab(tabKey)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${
                  tab === tabKey ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t(`transactions.tabs.${tabKey}`)}
              </button>
            ))}
          </div>
        </div>
        {tab === 'transactions' ? <TransactionsTab /> : <CategoriesTab />}
      </div>
    </>
  );
}

// ── Transactions tab ──────────────────────────────────────────────────────
function TransactionsTab() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [directionFilter, setDirectionFilter] = useState<TransactionDirection | 'all'>('all');

  const list = useCrudList<Transaction>({
    queryKey: ['transactions', directionFilter],
    fetcher: (p) =>
      finance.transactions.list(
        directionFilter === 'all' ? p : { ...p, direction: directionFilter },
      ),
    deleter: (id) => finance.transactions.remove(id),
  });
  const categories = useQuery({
    queryKey: ['tx-cats-all'],
    queryFn: () => finance.transactionCategories.list({ page_size: 200 }),
  });
  const wallets = useQuery({
    queryKey: ['wallets-for-tx'],
    queryFn: () => finance.wallets.list({ page_size: 200, is_active: true }),
  });

  const emptyForm: Partial<Transaction> = {
    direction: 'expense',
    category: '', title: '', amount: '0',
    occurred_on: new Date().toISOString().slice(0, 10),
    payment_method: 'cash', counterparty: '', reference: '', notes: '',
  };
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [form, setForm] = useState<Partial<Transaction>>(emptyForm);
  const [toDelete, setToDelete] = useState<Transaction | null>(null);
  const [newCat, setNewCat] = useState<{ open: boolean; name: string }>({ open: false, name: '' });

  const matchingCategories = (categories.data?.results ?? []).filter(
    (c) => c.direction === form.direction,
  );

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.transactions.update(editing.id, form) : finance.transactions.create(form),
    onSuccess: () => {
      toast.success(editing ? t('transactions.list.updated') : t('transactions.list.created'));
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: ['wallets'] });
      qc.invalidateQueries({ queryKey: ['wallets-all'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const createCategory = useMutation({
    mutationFn: () =>
      finance.transactionCategories.create({
        name: newCat.name.trim(),
        direction: form.direction,
        is_active: true,
      }),
    onSuccess: (cat) => {
      toast.success(t('transactions.list.categoryCreated'));
      qc.invalidateQueries({ queryKey: ['tx-cats-all'] });
      qc.invalidateQueries({ queryKey: ['tx-cats'] });
      setForm((f) => ({ ...f, category: cat.id }));
      setNewCat({ open: false, name: '' });
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate(direction: TransactionDirection = 'expense') {
    setEditing(null);
    const firstCat = (categories.data?.results ?? []).find((c) => c.direction === direction);
    setForm({ ...emptyForm, direction, category: firstCat?.id ?? '' });
    setNewCat({ open: false, name: '' });
    setOpen(true);
  }
  function openEdit(row: Transaction) {
    setEditing(row);
    setForm(row);
    setNewCat({ open: false, name: '' });
    setOpen(true);
  }
  function setDirection(direction: TransactionDirection) {
    const firstCat = (categories.data?.results ?? []).find((c) => c.direction === direction);
    setForm((f) => ({ ...f, direction, category: firstCat?.id ?? '' }));
  }

  const columns: Column<Transaction>[] = [
    { key: 'date', header: t('transactions.columns.date'), render: (r) => formatDate(r.occurred_on) },
    { key: 'dir', header: t('transactions.columns.direction'), render: (r) => (
      r.direction === 'income'
        ? <span className="badge-green">{t('transactions.directions.income')}</span>
        : <span className="badge-gray">{t('transactions.directions.expense')}</span>
    ) },
    { key: 'title', header: t('transactions.columns.title'), render: (r) => <span className="font-medium">{r.title}</span> },
    { key: 'cat', header: t('transactions.columns.category'), render: (r) => <span className="badge-gray">{r.category_name}</span> },
    { key: 'amount', header: t('transactions.columns.amount'), align: 'right', render: (r) => (
      <span className={`font-semibold ${r.direction === 'income' ? 'text-emerald-600' : 'text-slate-900'}`}>
        {r.direction === 'income' ? '+' : '−'}{formatMoney(r.amount)}
      </span>
    ) },
    { key: 'pay', header: t('transactions.columns.payment'), render: (r) => r.payment_method_display },
    { key: 'party', header: t('transactions.columns.counterparty'), render: (r) => r.counterparty || '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<Transaction>[] = [
    { key: 'occurred_on', header: t('transactions.exportCols.date'), value: (r) => r.occurred_on },
    { key: 'direction', header: t('transactions.exportCols.direction'), value: (r) => r.direction_display },
    { key: 'title', header: t('transactions.exportCols.title'), value: (r) => r.title },
    { key: 'category', header: t('transactions.exportCols.category'), value: (r) => r.category_name },
    { key: 'amount', header: t('transactions.exportCols.amount'), value: (r) => Number(r.amount) },
    { key: 'signed_amount', header: t('transactions.exportCols.signedAmount'), value: (r) => (r.direction === 'income' ? 1 : -1) * Number(r.amount) },
    { key: 'payment_method', header: t('transactions.exportCols.payment'), value: (r) => r.payment_method_display },
    { key: 'counterparty', header: t('transactions.exportCols.counterparty'), value: (r) => r.counterparty },
    { key: 'reference', header: t('transactions.exportCols.reference'), value: (r) => r.reference },
    { key: 'recorded_by', header: t('transactions.exportCols.recordedBy'), value: (r) => r.recorded_by_name ?? '' },
    { key: 'notes', header: t('transactions.exportCols.notes'), value: (r) => r.notes },
  ];

  const directionTabs: Array<TransactionDirection | 'all'> = ['all', 'income', 'expense'];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('transactions.list.searchPlaceholder')} />
          <div className="flex gap-1">
            {directionTabs.map((d) => (
              <button
                key={d}
                onClick={() => setDirectionFilter(d)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium ${
                  directionFilter === d ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t(`transactions.filters.${d}`)}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu
            filename="transactions"
            columns={exportColumns}
            fetchRows={() => fetchAllPaginated(
              (p) => finance.transactions.list(p),
              {
                ...(list.search ? { search: list.search } : {}),
                ...(directionFilter !== 'all' ? { direction: directionFilter } : {}),
              },
            )}
          />
          <button onClick={() => openCreate('income')} className="btn-secondary"><Plus size={16} /> {t('transactions.list.newIncome')}</button>
          <button onClick={() => openCreate('expense')} className="btn-primary"><Plus size={16} /> {t('transactions.list.newExpense')}</button>
        </div>
      </div>
      <DataTable
        columns={columns} data={list.data?.results}
        loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={ArrowLeftRight} title={t('transactions.list.emptyTitle')} description={t('transactions.list.emptyDescription')} />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? t('transactions.list.editModal') : t('transactions.list.newModal')}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={!form.title || !form.amount || !form.category || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">{t('transactions.fields.direction')}</label>
            <div className="flex gap-2">
              {(['income', 'expense'] as TransactionDirection[]).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDirection(d)}
                  className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border ${
                    form.direction === d
                      ? d === 'income'
                        ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                        : 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {t(`transactions.directions.${d}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('transactions.fields.title')}</label>
            <input className="input" value={form.title ?? ''} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="label">{t('transactions.fields.category')}</label>
              {!newCat.open && (
                <button
                  type="button"
                  onClick={() => setNewCat({ open: true, name: '' })}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800 inline-flex items-center gap-0.5"
                >
                  <Plus size={12} /> {t('transactions.fields.new')}
                </button>
              )}
            </div>
            {newCat.open ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  className="input flex-1"
                  placeholder={t('transactions.fields.categoryNamePlaceholder')}
                  value={newCat.name}
                  onChange={(e) => setNewCat((s) => ({ ...s, name: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newCat.name.trim() && !createCategory.isPending) {
                      e.preventDefault();
                      createCategory.mutate();
                    }
                    if (e.key === 'Escape') {
                      e.preventDefault();
                      setNewCat({ open: false, name: '' });
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn-primary px-3"
                  disabled={!newCat.name.trim() || createCategory.isPending}
                  onClick={() => createCategory.mutate()}
                >
                  {createCategory.isPending ? '…' : t('common.add')}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3"
                  onClick={() => setNewCat({ open: false, name: '' })}
                >
                  {t('common.cancel')}
                </button>
              </div>
            ) : (
              <select className="input" value={form.category ?? ''} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="">
                  {matchingCategories.length === 0 ? t('transactions.fields.noneYet') : t('common.select')}
                </option>
                {matchingCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="label">{t('transactions.fields.amount')}</label>
            <input type="number" step="0.01" className="input" value={form.amount ?? '0'} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('transactions.fields.date')}</label>
            <input type="date" className="input" value={form.occurred_on ?? ''} onChange={(e) => setForm({ ...form, occurred_on: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('transactions.fields.paymentMethod')}</label>
            <select className="input" value={form.payment_method ?? 'cash'} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
              <option value="cash">{t('transactions.fields.paymentMethods.cash')}</option>
              <option value="mobile_money">{t('transactions.fields.paymentMethods.mobile_money')}</option>
              <option value="card">{t('transactions.fields.paymentMethods.card')}</option>
              <option value="bank_transfer">{t('transactions.fields.paymentMethods.bank_transfer')}</option>
            </select>
          </div>
          <div>
            <label className="label">
              {t('transactions.fields.wallet')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <select
              className="input"
              value={form.wallet ?? ''}
              onChange={(e) => setForm({ ...form, wallet: e.target.value || null })}
            >
              <option value="">{t('transactions.fields.walletNone')}</option>
              {wallets.data?.results.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">
              {form.direction === 'income'
                ? t('transactions.fields.customerOptional')
                : t('transactions.fields.supplierOptional')}
            </label>
            <input className="input" value={form.counterparty ?? ''} onChange={(e) => setForm({ ...form, counterparty: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('transactions.fields.reference')}</label>
            <input className="input" value={form.reference ?? ''} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('transactions.fields.notes')}</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('transactions.list.deleteTitle')}
        message={t('transactions.list.deleteMessage', { title: toDelete?.title ?? '' })}
        confirmLabel={t('common.delete')}
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (!toDelete) return;
          list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
        }}
      />
    </>
  );
}

// ── Categories tab ────────────────────────────────────────────────────────
function CategoriesTab() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<TransactionCategory>({
    queryKey: ['tx-cats'],
    fetcher: (p) => finance.transactionCategories.list(p),
    deleter: (id) => finance.transactionCategories.remove(id),
  });

  const emptyForm: Partial<TransactionCategory> = { name: '', direction: 'expense', description: '', is_active: true };
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TransactionCategory | null>(null);
  const [form, setForm] = useState<Partial<TransactionCategory>>(emptyForm);
  const [toDelete, setToDelete] = useState<TransactionCategory | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.transactionCategories.update(editing.id, form) : finance.transactionCategories.create(form),
    onSuccess: () => {
      toast.success(editing ? t('transactions.categories.updated') : t('transactions.categories.created'));
      qc.invalidateQueries({ queryKey: ['tx-cats'] });
      qc.invalidateQueries({ queryKey: ['tx-cats-all'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const columns: Column<TransactionCategory>[] = [
    { key: 'name', header: t('transactions.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'dir', header: t('transactions.columns.direction'), render: (r) => (
      r.direction === 'income'
        ? <span className="badge-green">{t('transactions.directions.income')}</span>
        : <span className="badge-gray">{t('transactions.directions.expense')}</span>
    ) },
    { key: 'desc', header: t('transactions.columns.description'), render: (r) => r.description || '—' },
    { key: 'status', header: t('transactions.columns.status'), render: (r) =>
      r.is_active
        ? <span className="badge-green">{t('common.active')}</span>
        : <span className="badge-gray">{t('common.off')}</span>
    },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); setEditing(r); setForm(r); setOpen(true); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<TransactionCategory>[] = [
    { key: 'name', header: t('transactions.exportCols.name'), value: (r) => r.name },
    { key: 'direction', header: t('transactions.exportCols.direction'), value: (r) => r.direction_display },
    { key: 'description', header: t('transactions.exportCols.description'), value: (r) => r.description },
    { key: 'is_active', header: t('transactions.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('transactions.categories.searchPlaceholder')} />
        <div className="flex items-center gap-2">
          <ExportMenu
            filename="transaction-categories"
            columns={exportColumns}
            fetchRows={() => fetchAllPaginated(
              (p) => finance.transactionCategories.list(p),
              list.search ? { search: list.search } : {},
            )}
          />
          <button onClick={() => { setEditing(null); setForm(emptyForm); setOpen(true); }} className="btn-primary">
            <Plus size={16} /> {t('transactions.categories.new')}
          </button>
        </div>
      </div>
      <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={Folder} title={t('transactions.categories.emptyTitle')} />} />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('transactions.categories.editModal') : t('transactions.categories.newModal')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button className="btn-primary" disabled={!form.name || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="label">{t('transactions.fields.direction')}</label>
            <div className="flex gap-2">
              {(['income', 'expense'] as TransactionDirection[]).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setForm({ ...form, direction: d })}
                  className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border ${
                    form.direction === d
                      ? d === 'income'
                        ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                        : 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {t(`transactions.directions.${d}`)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">{t('transactions.fields.name')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('transactions.fields.description')}</label>
            <textarea className="input" rows={2} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title={t('transactions.categories.deleteTitle')} message={t('transactions.categories.deleteMessage', { name: toDelete?.name ?? '' })}
        confirmLabel={t('common.delete')} loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
