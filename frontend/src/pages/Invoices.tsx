import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, FileText, CreditCard, Send, XCircle } from 'lucide-react';
import { toast } from 'sonner';

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
import type { Invoice } from '@/api/types';

const STATUS_CLASSES: Record<string, string> = {
  draft: 'badge-gray', sent: 'badge-blue', partially_paid: 'badge-yellow',
  paid: 'badge-green', overdue: 'badge-red', cancelled: 'badge-gray',
};

const emptyForm: Partial<Invoice> = {
  invoice_number: '', customer_name: '', customer_email: '', customer_phone: '',
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10),
  amount: '0', description: '', notes: '', status: 'draft',
};

export function InvoicesPage() {
  const qc = useQueryClient();
  const list = useCrudList<Invoice>({
    queryKey: ['invoices'],
    fetcher: (p) => finance.invoices.list(p),
    deleter: (id) => finance.invoices.remove(id),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Invoice | null>(null);
  const [form, setForm] = useState<Partial<Invoice>>(emptyForm);
  const [paying, setPaying] = useState<Invoice | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [toDelete, setToDelete] = useState<Invoice | null>(null);

  function nextInvoiceNumber(): string {
    const now = new Date();
    return `INV-${now.getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
  }

  const save = useMutation({
    mutationFn: () =>
      editing ? finance.invoices.update(editing.id, form) : finance.invoices.create(form),
    onSuccess: () => {
      toast.success(editing ? 'Invoice updated.' : 'Invoice created.');
      qc.invalidateQueries({ queryKey: ['invoices'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const recordPayment = useMutation({
    mutationFn: () => finance.invoices.recordPayment(paying!.id, Number(paymentAmount)),
    onSuccess: () => {
      toast.success('Payment recorded.');
      qc.invalidateQueries({ queryKey: ['invoices'] });
      setPaying(null); setPaymentAmount('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const markSent = useMutation({
    mutationFn: (id: string) => finance.invoices.markSent(id),
    onSuccess: () => { toast.success('Marked as sent.'); qc.invalidateQueries({ queryKey: ['invoices'] }); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const cancel = useMutation({
    mutationFn: (id: string) => finance.invoices.cancel(id),
    onSuccess: () => { toast.success('Cancelled.'); qc.invalidateQueries({ queryKey: ['invoices'] }); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, invoice_number: nextInvoiceNumber() });
    setOpen(true);
  }
  function openEdit(row: Invoice) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<Invoice>[] = [
    { key: 'inv', header: 'Invoice', render: (r) => <span className="font-mono text-xs">{r.invoice_number}</span> },
    { key: 'cust', header: 'Customer', render: (r) => <span className="font-medium">{r.customer_name}</span> },
    { key: 'issue', header: 'Issued', render: (r) => formatDate(r.issue_date) },
    { key: 'due', header: 'Due', render: (r) => (
      <span className={r.is_overdue ? 'text-red-600 font-medium' : ''}>{formatDate(r.due_date)}</span>
    )},
    { key: 'amount', header: 'Amount', align: 'right', render: (r) => formatMoney(r.amount) },
    { key: 'paid', header: 'Paid', align: 'right', render: (r) => formatMoney(r.amount_paid) },
    { key: 'balance', header: 'Balance', align: 'right', render: (r) => (
      <span className="font-semibold">{formatMoney(r.balance_due)}</span>
    )},
    { key: 'status', header: 'Status', render: (r) => (
      <span className={STATUS_CLASSES[r.status] ?? 'badge-gray'}>{r.status_display}</span>
    )},
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'draft' && (
          <button className="btn-ghost p-1.5 text-blue-600" title="Mark as sent" onClick={(e) => { e.stopPropagation(); markSent.mutate(r.id); }}>
            <Send size={14} />
          </button>
        )}
        {!['paid', 'cancelled'].includes(r.status) && (
          <button className="btn-ghost p-1.5 text-emerald-700" title="Record payment" onClick={(e) => { e.stopPropagation(); setPaying(r); setPaymentAmount(String(r.balance_due)); }}>
            <CreditCard size={14} />
          </button>
        )}
        {!['paid', 'cancelled'].includes(r.status) && (
          <button className="btn-ghost p-1.5 text-amber-700" title="Cancel" onClick={(e) => { e.stopPropagation(); cancel.mutate(r.id); }}>
            <XCircle size={14} />
          </button>
        )}
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<Invoice>[] = [
    { key: 'invoice_number', header: 'Invoice #', value: (r) => r.invoice_number },
    { key: 'customer_name', header: 'Customer', value: (r) => r.customer_name },
    { key: 'customer_email', header: 'Email', value: (r) => r.customer_email },
    { key: 'customer_phone', header: 'Phone', value: (r) => r.customer_phone },
    { key: 'issue_date', header: 'Issued', value: (r) => r.issue_date },
    { key: 'due_date', header: 'Due', value: (r) => r.due_date },
    { key: 'amount', header: 'Amount', value: (r) => Number(r.amount) },
    { key: 'amount_paid', header: 'Paid', value: (r) => Number(r.amount_paid) },
    { key: 'balance_due', header: 'Balance', value: (r) => Number(r.balance_due) },
    { key: 'status', header: 'Status', value: (r) => r.status_display },
    { key: 'is_overdue', header: 'Overdue', value: (r) => (r.is_overdue ? 'yes' : 'no') },
    { key: 'paid_at', header: 'Paid at', value: (r) => r.paid_at ?? '' },
    { key: 'description', header: 'Description', value: (r) => r.description },
    { key: 'notes', header: 'Notes', value: (r) => r.notes },
  ];

  return (
    <>
      <PageHeader
        title="Invoices"
        subtitle="Outbound invoicing and payment follow-up"
        actions={
          <>
            <ExportMenu
              filename="invoices"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => finance.invoices.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> New invoice</button>
          </>
        }
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search invoices…" />
        </div>
        <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
          empty={<EmptyState icon={FileText} title="No invoices yet" />} />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? 'Edit invoice' : 'New invoice'} size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={!form.customer_name || !form.invoice_number || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Invoice #</label>
            <input className="input font-mono" value={form.invoice_number ?? ''} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
          </div>
          <div>
            <label className="label">Status</label>
            <select className="input" value={form.status ?? 'draft'} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="draft">Draft</option>
              <option value="sent">Sent</option>
              <option value="partially_paid">Partially paid</option>
              <option value="paid">Paid</option>
              <option value="overdue">Overdue</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">Customer name</label>
            <input className="input" value={form.customer_name ?? ''} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input" value={form.customer_email ?? ''} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.customer_phone ?? ''} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} />
          </div>
          <div>
            <label className="label">Issue date</label>
            <input type="date" className="input" value={form.issue_date ?? ''} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
          </div>
          <div>
            <label className="label">Due date</label>
            <input type="date" className="input" value={form.due_date ?? ''} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          </div>
          <div>
            <label className="label">Amount</label>
            <input type="number" step="0.01" className="input" value={form.amount ?? '0'} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <label className="label">Amount paid</label>
            <input type="number" step="0.01" className="input" value={form.amount_paid ?? '0'} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Description</label>
            <textarea className="input" rows={2} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
      </Modal>

      <Modal
        open={!!paying} onClose={() => setPaying(null)}
        title={`Record payment — ${paying?.invoice_number ?? ''}`}
        size="sm"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setPaying(null)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!paymentAmount || Number(paymentAmount) <= 0 || recordPayment.isPending}
              onClick={() => recordPayment.mutate()}
            >
              {recordPayment.isPending ? 'Saving…' : 'Record'}
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-500 mb-3">
          Outstanding balance: <strong>{formatMoney(paying?.balance_due ?? 0)}</strong>.
        </p>
        <div>
          <label className="label">Amount received</label>
          <input
            type="number" step="0.01" autoFocus
            className="input" value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
          />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title="Delete invoice?" message={`Permanently remove ${toDelete?.invoice_number}?`}
        confirmLabel="Delete" loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
