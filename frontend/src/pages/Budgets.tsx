import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Receipt } from 'lucide-react';
import { toast } from 'sonner';

import { finance } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
import type { Budget } from '@/api/types';

const emptyForm: Partial<Budget> = {
  category: '',
  month: new Date(Date.now()).toISOString().slice(0, 7) + '-01',
  amount: '0',
  notes: '',
};

export function BudgetsPage() {
  const qc = useQueryClient();
  const list = useCrudList<Budget>({
    queryKey: ['budgets'],
    fetcher: (p) => finance.budgets.list(p),
    deleter: (id) => finance.budgets.remove(id),
  });
  const categories = useQuery({
    queryKey: ['expense-cats-all'],
    queryFn: () => finance.expenseCategories.list({ page_size: 200 }),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Budget | null>(null);
  const [form, setForm] = useState<Partial<Budget>>(emptyForm);
  const [toDelete, setToDelete] = useState<Budget | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.budgets.update(editing.id, form) : finance.budgets.create(form),
    onSuccess: () => {
      toast.success(editing ? 'Budget updated.' : 'Budget created.');
      qc.invalidateQueries({ queryKey: ['budgets'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, category: categories.data?.results[0]?.id ?? '' });
    setOpen(true);
  }
  function openEdit(row: Budget) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<Budget>[] = [
    { key: 'cat', header: 'Category', render: (r) => <span className="font-medium">{r.category_name}</span> },
    { key: 'month', header: 'Month', render: (r) => formatDate(r.month, { year: 'numeric', month: 'long' }) },
    { key: 'amount', header: 'Budgeted', align: 'right', render: (r) => <span className="font-semibold">{formatMoney(r.amount)}</span> },
    { key: 'notes', header: 'Notes', render: (r) => r.notes || '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<Budget>[] = [
    { key: 'category', header: 'Category', value: (r) => r.category_name },
    { key: 'month', header: 'Month', value: (r) => r.month },
    { key: 'amount', header: 'Budgeted', value: (r) => Number(r.amount) },
    { key: 'notes', header: 'Notes', value: (r) => r.notes },
  ];

  return (
    <>
      <PageHeader
        title="Budgets"
        subtitle="Monthly spending caps per expense category"
        actions={
          <>
            <ExportMenu
              filename="budgets"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated((p) => finance.budgets.list(p))}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> New budget</button>
          </>
        }
      />
      <div className="card">
        <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
          empty={<EmptyState icon={Receipt} title="No budgets defined" description="Set monthly caps to monitor spending." />} />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? 'Edit budget' : 'New budget'}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={!form.category || !form.amount || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">Category</label>
            <select className="input" value={form.category ?? ''} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              <option value="">— Select —</option>
              {categories.data?.results.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Month (1st day)</label>
            <input type="date" className="input" value={form.month ?? ''} onChange={(e) => setForm({ ...form, month: e.target.value })} />
          </div>
          <div>
            <label className="label">Amount</label>
            <input type="number" step="0.01" className="input" value={form.amount ?? '0'} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title="Delete budget?" message="This will remove the budget entry."
        confirmLabel="Delete" loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
