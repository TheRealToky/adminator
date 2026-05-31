import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Wallet, Folder } from 'lucide-react';
import { toast } from 'sonner';

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
import { formatDate, formatMoney } from '@/lib/format';
import type { Expense, ExpenseCategory } from '@/api/types';

type Tab = 'expenses' | 'categories';

export function ExpensesPage() {
  const [tab, setTab] = useState<Tab>('expenses');
  return (
    <>
      <PageHeader title="Expenses" subtitle="Operating costs by category" />
      <div className="card">
        <div className="card-header">
          <div className="flex gap-1">
            {(['expenses', 'categories'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${
                  tab === t ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t}
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
      toast.success(editing ? 'Expense updated.' : 'Expense recorded.');
      qc.invalidateQueries({ queryKey: ['expenses'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const createCategory = useMutation({
    mutationFn: () => finance.expenseCategories.create({ name: newCat.name.trim(), is_active: true }),
    onSuccess: (cat) => {
      toast.success('Category created.');
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
    { key: 'date', header: 'Date', render: (r) => formatDate(r.incurred_on) },
    { key: 'title', header: 'Title', render: (r) => <span className="font-medium">{r.title}</span> },
    { key: 'cat', header: 'Category', render: (r) => <span className="badge-gray">{r.category_name}</span> },
    { key: 'amount', header: 'Amount', align: 'right', render: (r) => <span className="font-semibold">{formatMoney(r.amount)}</span> },
    { key: 'pay', header: 'Payment', render: (r) => r.payment_method_display },
    { key: 'sup', header: 'Supplier', render: (r) => r.supplier_name ?? '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search expenses…" />
        <button onClick={openCreate} className="btn-primary"><Plus size={16} /> Record expense</button>
      </div>
      <DataTable
        columns={columns} data={list.data?.results}
        loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={Wallet} title="No expenses recorded" description="Track operating costs as they happen." />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? 'Edit expense' : 'Record expense'}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!form.title || !form.amount || !form.category || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">Title</label>
            <input className="input" value={form.title ?? ''} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="label">Category</label>
              {!newCat.open && (
                <button
                  type="button"
                  onClick={() => setNewCat({ open: true, name: '' })}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800 inline-flex items-center gap-0.5"
                >
                  <Plus size={12} /> New
                </button>
              )}
            </div>
            {newCat.open ? (
              <div className="flex gap-2">
                <input
                  autoFocus
                  className="input flex-1"
                  placeholder="Category name"
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
                  {createCategory.isPending ? '…' : 'Add'}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3"
                  onClick={() => setNewCat({ open: false, name: '' })}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <select className="input" value={form.category ?? ''} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="">
                  {categories.data && categories.data.results.length === 0 ? '— None yet — click + New —' : '— Select —'}
                </option>
                {categories.data?.results.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="label">Amount</label>
            <input type="number" step="0.01" className="input" value={form.amount ?? '0'} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <label className="label">Date</label>
            <input type="date" className="input" value={form.incurred_on ?? ''} onChange={(e) => setForm({ ...form, incurred_on: e.target.value })} />
          </div>
          <div>
            <label className="label">Payment method</label>
            <select className="input" value={form.payment_method ?? 'cash'} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
              <option value="cash">Cash</option>
              <option value="mobile_money">Mobile Money</option>
              <option value="card">Card</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">Supplier (optional)</label>
            <select className="input" value={form.supplier ?? ''} onChange={(e) => setForm({ ...form, supplier: e.target.value || null })}>
              <option value="">— None —</option>
              {suppliers.data?.results.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Reference / receipt #</label>
            <input className="input" value={form.reference ?? ''} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title="Delete expense?"
        message={`Remove "${toDelete?.title}"?`}
        confirmLabel="Delete"
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
      toast.success(editing ? 'Category updated.' : 'Category created.');
      qc.invalidateQueries({ queryKey: ['expense-cats'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const columns: Column<ExpenseCategory>[] = [
    { key: 'name', header: 'Name', render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'desc', header: 'Description', render: (r) => r.description || '—' },
    { key: 'status', header: 'Status', render: (r) =>
      r.is_active ? <span className="badge-green">Active</span> : <span className="badge-gray">Off</span>
    },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); setEditing(r); setForm(r); setOpen(true); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search categories…" />
        <button onClick={() => { setEditing(null); setForm({ name: '', description: '', is_active: true }); setOpen(true); }} className="btn-primary">
          <Plus size={16} /> New category
        </button>
      </div>
      <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
        empty={<EmptyState icon={Folder} title="No categories yet" />} />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? 'Edit category' : 'New category'}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={!form.name || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input" rows={2} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title="Delete category?" message={`Remove "${toDelete?.name}"?`}
        confirmLabel="Delete" loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
