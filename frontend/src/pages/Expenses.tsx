import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Wallet, Folder } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { catalog, finance } from '@/api/endpoints';
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
import type { Expense, ExpenseCategory } from '@/api/types';

type Tab = 'expenses' | 'categories';

export function ExpensesPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('expenses');
  return (
    <>
      <PageHeader title={t('expenses.title')} subtitle={t('expenses.subtitle')} />
      <div className="card">
        <div className="card-header">
          <div className="flex gap-1">
            {(['expenses', 'categories'] as Tab[]).map((tabKey) => (
              <button
                key={tabKey}
                onClick={() => setTab(tabKey)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${
                  tab === tabKey ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t(`expenses.tabs.${tabKey}`)}
              </button>
            ))}
          </div>
        </div>
        {tab === 'expenses' ? <ExpensesTab /> : <CategoriesTab />}
      </div>
    </>
  );
}

// ── Expenses tab ──────────────────────────────────────────────────────────
function ExpensesTab() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Expense>({
    queryKey: ['expenses'],
    fetcher: (p) => finance.expenses.list(p),
    deleter: (id) => finance.expenses.remove(id),
  });
  const categories = useQuery({
    queryKey: ['expense-cats-all'],
    queryFn: () => finance.expenseCategories.list({ page_size: 200 }),
  });
  const suppliers = useQuery({
    queryKey: ['suppliers-all'],
    queryFn: () => catalog.suppliers.list({ page_size: 200 }),
  });

  const emptyForm: Partial<Expense> = {
    category: '', title: '', amount: '0',
    incurred_on: new Date().toISOString().slice(0, 10),
    payment_method: 'cash', supplier: null, reference: '', notes: '',
  };
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [form, setForm] = useState<Partial<Expense>>(emptyForm);
  const [toDelete, setToDelete] = useState<Expense | null>(null);
  const [newCat, setNewCat] = useState<{ open: boolean; name: string }>({ open: false, name: '' });

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.expenses.update(editing.id, form) : finance.expenses.create(form),
    onSuccess: () => {
      toast.success(editing ? t('expenses.list.updated') : t('expenses.list.created'));
      qc.invalidateQueries({ queryKey: ['expenses'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const createCategory = useMutation({
    mutationFn: () => finance.expenseCategories.create({ name: newCat.name.trim(), is_active: true }),
    onSuccess: (cat) => {
      toast.success(t('expenses.list.categoryCreated'));
      qc.invalidateQueries({ queryKey: ['expense-cats-all'] });
      qc.invalidateQueries({ queryKey: ['expense-cats'] });
      setForm((f) => ({ ...f, category: cat.id }));
      setNewCat({ open: false, name: '' });
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, category: categories.data?.results[0]?.id ?? '' });
    setNewCat({ open: false, name: '' });
    setOpen(true);
  }
  function openEdit(row: Expense) {
    setEditing(row);
    setForm(row);
    setNewCat({ open: false, name: '' });
    setOpen(true);
  }

  const columns: Column<Expense>[] = [
    { key: 'date', header: t('expenses.columns.date'), render: (r) => formatDate(r.incurred_on) },
    { key: 'title', header: t('expenses.columns.title'), render: (r) => <span className="font-medium">{r.title}</span> },
    { key: 'cat', header: t('expenses.columns.category'), render: (r) => <span className="badge-gray">{r.category_name}</span> },
    { key: 'amount', header: t('expenses.columns.amount'), align: 'right', render: (r) => <span className="font-semibold">{formatMoney(r.amount)}</span> },
    { key: 'pay', header: t('expenses.columns.payment'), render: (r) => r.payment_method_display },
    { key: 'sup', header: t('expenses.columns.supplier'), render: (r) => r.supplier_name ?? '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<Expense>[] = [
    { key: 'incurred_on', header: t('expenses.exportCols.date'), value: (r) => r.incurred_on },
    { key: 'title', header: t('expenses.exportCols.title'), value: (r) => r.title },
    { key: 'category', header: t('expenses.exportCols.category'), value: (r) => r.category_name },
    { key: 'amount', header: t('expenses.exportCols.amount'), value: (r) => Number(r.amount) },
    { key: 'payment_method', header: t('expenses.exportCols.payment'), value: (r) => r.payment_method_display },
    { key: 'supplier', header: t('expenses.exportCols.supplier'), value: (r) => r.supplier_name ?? '' },
    { key: 'reference', header: t('expenses.exportCols.reference'), value: (r) => r.reference },
    { key: 'recorded_by', header: t('expenses.exportCols.recordedBy'), value: (r) => r.recorded_by_name ?? '' },
    { key: 'notes', header: t('expenses.exportCols.notes'), value: (r) => r.notes },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('expenses.list.searchPlaceholder')} />
        <div className="flex items-center gap-2">
          <ExportMenu
            filename="expenses"
            columns={exportColumns}
            fetchRows={() => fetchAllPaginated(
              (p) => finance.expenses.list(p),
              list.search ? { search: list.search } : {},
            )}
          />
          <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('expenses.list.new')}</button>
        </div>
      </div>
      <DataTable
        columns={columns} data={list.data?.results}
        loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={Wallet} title={t('expenses.list.emptyTitle')} description={t('expenses.list.emptyDescription')} />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? t('expenses.list.editModal') : t('expenses.list.newModal')}
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
            <label className="label">{t('expenses.fields.title')}</label>
            <input className="input" value={form.title ?? ''} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="label">{t('expenses.fields.category')}</label>
              {!newCat.open && (
                <button
                  type="button"
                  onClick={() => setNewCat({ open: true, name: '' })}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800 inline-flex items-center gap-0.5"
                >
                  <Plus size={12} /> {t('expenses.fields.new')}
                </button>
              )}
            </div>
            {newCat.open ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  className="input flex-1"
                  placeholder={t('expenses.fields.categoryNamePlaceholder')}
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
                  {categories.data && categories.data.results.length === 0 ? t('expenses.fields.noneYet') : t('common.select')}
                </option>
                {categories.data?.results.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="label">{t('expenses.fields.amount')}</label>
            <input type="number" step="0.01" className="input" value={form.amount ?? '0'} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('expenses.fields.date')}</label>
            <input type="date" className="input" value={form.incurred_on ?? ''} onChange={(e) => setForm({ ...form, incurred_on: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('expenses.fields.paymentMethod')}</label>
            <select className="input" value={form.payment_method ?? 'cash'} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
              <option value="cash">{t('expenses.fields.paymentMethods.cash')}</option>
              <option value="mobile_money">{t('expenses.fields.paymentMethods.mobile_money')}</option>
              <option value="card">{t('expenses.fields.paymentMethods.card')}</option>
              <option value="bank_transfer">{t('expenses.fields.paymentMethods.bank_transfer')}</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('expenses.fields.supplierOptional')}</label>
            <select className="input" value={form.supplier ?? ''} onChange={(e) => setForm({ ...form, supplier: e.target.value || null })}>
              <option value="">{t('common.none')}</option>
              {suppliers.data?.results.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t('expenses.fields.reference')}</label>
            <input className="input" value={form.reference ?? ''} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('expenses.fields.notes')}</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('expenses.list.deleteTitle')}
        message={t('expenses.list.deleteMessage', { title: toDelete?.title ?? '' })}
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
  const list = useCrudList<ExpenseCategory>({
    queryKey: ['expense-cats'],
    fetcher: (p) => finance.expenseCategories.list(p),
    deleter: (id) => finance.expenseCategories.remove(id),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ExpenseCategory | null>(null);
  const [form, setForm] = useState<Partial<ExpenseCategory>>({ name: '', description: '', is_active: true });
  const [toDelete, setToDelete] = useState<ExpenseCategory | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.expenseCategories.update(editing.id, form) : finance.expenseCategories.create(form),
    onSuccess: () => {
      toast.success(editing ? t('expenses.categories.updated') : t('expenses.categories.created'));
      qc.invalidateQueries({ queryKey: ['expense-cats'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const columns: Column<ExpenseCategory>[] = [
    { key: 'name', header: t('expenses.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'desc', header: t('expenses.columns.description'), render: (r) => r.description || '—' },
    { key: 'status', header: t('expenses.columns.status'), render: (r) =>
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

  const exportColumns: ExportColumn<ExpenseCategory>[] = [
    { key: 'name', header: t('expenses.exportCols.name'), value: (r) => r.name },
    { key: 'description', header: t('expenses.exportCols.description'), value: (r) => r.description },
    { key: 'is_active', header: t('expenses.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('expenses.categories.searchPlaceholder')} />
        <div className="flex items-center gap-2">
          <ExportMenu
            filename="expense-categories"
            columns={exportColumns}
            fetchRows={() => fetchAllPaginated(
              (p) => finance.expenseCategories.list(p),
              list.search ? { search: list.search } : {},
            )}
          />
          <button onClick={() => { setEditing(null); setForm({ name: '', description: '', is_active: true }); setOpen(true); }} className="btn-primary">
            <Plus size={16} /> {t('expenses.categories.new')}
          </button>
        </div>
      </div>
      <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={Folder} title={t('expenses.categories.emptyTitle')} />} />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('expenses.categories.editModal') : t('expenses.categories.newModal')}
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
            <label className="label">{t('expenses.fields.name')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('expenses.fields.description')}</label>
            <textarea className="input" rows={2} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title={t('expenses.categories.deleteTitle')} message={t('expenses.categories.deleteMessage', { name: toDelete?.name ?? '' })}
        confirmLabel={t('common.delete')} loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
