import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, FileText, CreditCard, Send, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { finance } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
const STATUS_CLASSES = {
    draft: 'badge-gray', sent: 'badge-blue', partially_paid: 'badge-yellow',
    paid: 'badge-green', overdue: 'badge-red', cancelled: 'badge-gray',
};
const emptyForm = {
    invoice_number: '', customer_name: '', customer_email: '', customer_phone: '',
    issue_date: new Date().toISOString().slice(0, 10),
    due_date: new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10),
    amount: '0', description: '', notes: '', status: 'draft',
};
export function InvoicesPage() {
    const qc = useQueryClient();
    const list = useCrudList({
        queryKey: ['invoices'],
        fetcher: (p) => finance.invoices.list(p),
        deleter: (id) => finance.invoices.remove(id),
    });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [paying, setPaying] = useState(null);
    const [paymentAmount, setPaymentAmount] = useState('');
    const [toDelete, setToDelete] = useState(null);
    function nextInvoiceNumber() {
        const now = new Date();
        return `INV-${now.getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
    }
    const save = useMutation({
        mutationFn: () => editing ? finance.invoices.update(editing.id, form) : finance.invoices.create(form),
        onSuccess: () => {
            toast.success(editing ? 'Invoice updated.' : 'Invoice created.');
            qc.invalidateQueries({ queryKey: ['invoices'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const recordPayment = useMutation({
        mutationFn: () => finance.invoices.recordPayment(paying.id, Number(paymentAmount)),
        onSuccess: () => {
            toast.success('Payment recorded.');
            qc.invalidateQueries({ queryKey: ['invoices'] });
            setPaying(null);
            setPaymentAmount('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const markSent = useMutation({
        mutationFn: (id) => finance.invoices.markSent(id),
        onSuccess: () => { toast.success('Marked as sent.'); qc.invalidateQueries({ queryKey: ['invoices'] }); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const cancel = useMutation({
        mutationFn: (id) => finance.invoices.cancel(id),
        onSuccess: () => { toast.success('Cancelled.'); qc.invalidateQueries({ queryKey: ['invoices'] }); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() {
        setEditing(null);
        setForm({ ...emptyForm, invoice_number: nextInvoiceNumber() });
        setOpen(true);
    }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'inv', header: 'Invoice', render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.invoice_number }) },
        { key: 'cust', header: 'Customer', render: (r) => _jsx("span", { className: "font-medium", children: r.customer_name }) },
        { key: 'issue', header: 'Issued', render: (r) => formatDate(r.issue_date) },
        { key: 'due', header: 'Due', render: (r) => (_jsx("span", { className: r.is_overdue ? 'text-red-600 font-medium' : '', children: formatDate(r.due_date) })) },
        { key: 'amount', header: 'Amount', align: 'right', render: (r) => formatMoney(r.amount) },
        { key: 'paid', header: 'Paid', align: 'right', render: (r) => formatMoney(r.amount_paid) },
        { key: 'balance', header: 'Balance', align: 'right', render: (r) => (_jsx("span", { className: "font-semibold", children: formatMoney(r.balance_due) })) },
        { key: 'status', header: 'Status', render: (r) => (_jsx("span", { className: STATUS_CLASSES[r.status] ?? 'badge-gray', children: r.status_display })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [r.status === 'draft' && (_jsx("button", { className: "btn-ghost p-1.5 text-blue-600", title: "Mark as sent", onClick: (e) => { e.stopPropagation(); markSent.mutate(r.id); }, children: _jsx(Send, { size: 14 }) })), !['paid', 'cancelled'].includes(r.status) && (_jsx("button", { className: "btn-ghost p-1.5 text-emerald-700", title: "Record payment", onClick: (e) => { e.stopPropagation(); setPaying(r); setPaymentAmount(String(r.balance_due)); }, children: _jsx(CreditCard, { size: 14 }) })), !['paid', 'cancelled'].includes(r.status) && (_jsx("button", { className: "btn-ghost p-1.5 text-amber-700", title: "Cancel", onClick: (e) => { e.stopPropagation(); cancel.mutate(r.id); }, children: _jsx(XCircle, { size: 14 }) })), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
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
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Invoices", subtitle: "Outbound invoicing and payment follow-up", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "invoices", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.invoices.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New invoice"] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search invoices\u2026" }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: FileText, title: "No invoices yet" }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? 'Edit invoice' : 'New invoice', size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !form.customer_name || !form.invoice_number || save.isPending, onClick: () => save.mutate(), children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "Invoice #" }), _jsx("input", { className: "input font-mono", value: form.invoice_number ?? '', onChange: (e) => setForm({ ...form, invoice_number: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Status" }), _jsxs("select", { className: "input", value: form.status ?? 'draft', onChange: (e) => setForm({ ...form, status: e.target.value }), children: [_jsx("option", { value: "draft", children: "Draft" }), _jsx("option", { value: "sent", children: "Sent" }), _jsx("option", { value: "partially_paid", children: "Partially paid" }), _jsx("option", { value: "paid", children: "Paid" }), _jsx("option", { value: "overdue", children: "Overdue" }), _jsx("option", { value: "cancelled", children: "Cancelled" })] })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Customer name" }), _jsx("input", { className: "input", value: form.customer_name ?? '', onChange: (e) => setForm({ ...form, customer_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Email" }), _jsx("input", { type: "email", className: "input", value: form.customer_email ?? '', onChange: (e) => setForm({ ...form, customer_email: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Phone" }), _jsx("input", { className: "input", value: form.customer_phone ?? '', onChange: (e) => setForm({ ...form, customer_phone: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Issue date" }), _jsx("input", { type: "date", className: "input", value: form.issue_date ?? '', onChange: (e) => setForm({ ...form, issue_date: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Due date" }), _jsx("input", { type: "date", className: "input", value: form.due_date ?? '', onChange: (e) => setForm({ ...form, due_date: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Amount" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount ?? '0', onChange: (e) => setForm({ ...form, amount: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Amount paid" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount_paid ?? '0', onChange: (e) => setForm({ ...form, amount_paid: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Description" }), _jsx("textarea", { className: "input", rows: 2, value: form.description ?? '', onChange: (e) => setForm({ ...form, description: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Notes" }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsxs(Modal, { open: !!paying, onClose: () => setPaying(null), title: `Record payment — ${paying?.invoice_number ?? ''}`, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setPaying(null), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !paymentAmount || Number(paymentAmount) <= 0 || recordPayment.isPending, onClick: () => recordPayment.mutate(), children: recordPayment.isPending ? 'Saving…' : 'Record' })] }), children: [_jsxs("p", { className: "text-sm text-slate-500 mb-3", children: ["Outstanding balance: ", _jsx("strong", { children: formatMoney(paying?.balance_due ?? 0) }), "."] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Amount received" }), _jsx("input", { type: "number", step: "0.01", autoFocus: true, className: "input", value: paymentAmount, onChange: (e) => setPaymentAmount(e.target.value) })] })] }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete invoice?", message: `Permanently remove ${toDelete?.invoice_number}?`, confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
