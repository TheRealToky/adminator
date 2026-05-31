import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, FileText, CreditCard, Send, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';
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
    const { t } = useTranslation();
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
            toast.success(editing ? t('invoices.updated') : t('invoices.created'));
            qc.invalidateQueries({ queryKey: ['invoices'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const recordPayment = useMutation({
        mutationFn: () => finance.invoices.recordPayment(paying.id, Number(paymentAmount)),
        onSuccess: () => {
            toast.success(t('invoices.paymentRecorded'));
            qc.invalidateQueries({ queryKey: ['invoices'] });
            setPaying(null);
            setPaymentAmount('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const markSent = useMutation({
        mutationFn: (id) => finance.invoices.markSent(id),
        onSuccess: () => { toast.success(t('invoices.markedSent')); qc.invalidateQueries({ queryKey: ['invoices'] }); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const cancel = useMutation({
        mutationFn: (id) => finance.invoices.cancel(id),
        onSuccess: () => { toast.success(t('invoices.cancelled')); qc.invalidateQueries({ queryKey: ['invoices'] }); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() {
        setEditing(null);
        setForm({ ...emptyForm, invoice_number: nextInvoiceNumber() });
        setOpen(true);
    }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'inv', header: t('invoices.columns.invoice'), render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.invoice_number }) },
        { key: 'cust', header: t('invoices.columns.customer'), render: (r) => _jsx("span", { className: "font-medium", children: r.customer_name }) },
        { key: 'issue', header: t('invoices.columns.issued'), render: (r) => formatDate(r.issue_date) },
        { key: 'due', header: t('invoices.columns.due'), render: (r) => (_jsx("span", { className: r.is_overdue ? 'text-red-600 font-medium' : '', children: formatDate(r.due_date) })) },
        { key: 'amount', header: t('invoices.columns.amount'), align: 'right', render: (r) => formatMoney(r.amount) },
        { key: 'paid', header: t('invoices.columns.paid'), align: 'right', render: (r) => formatMoney(r.amount_paid) },
        { key: 'balance', header: t('invoices.columns.balance'), align: 'right', render: (r) => (_jsx("span", { className: "font-semibold", children: formatMoney(r.balance_due) })) },
        { key: 'status', header: t('invoices.columns.status'), render: (r) => (_jsx("span", { className: STATUS_CLASSES[r.status] ?? 'badge-gray', children: r.status_display })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [r.status === 'draft' && (_jsx("button", { className: "btn-ghost p-1.5 text-blue-600", title: t('invoices.actions.markAsSent'), onClick: (e) => { e.stopPropagation(); markSent.mutate(r.id); }, children: _jsx(Send, { size: 14 }) })), !['paid', 'cancelled'].includes(r.status) && (_jsx("button", { className: "btn-ghost p-1.5 text-emerald-700", title: t('invoices.actions.recordPayment'), onClick: (e) => { e.stopPropagation(); setPaying(r); setPaymentAmount(String(r.balance_due)); }, children: _jsx(CreditCard, { size: 14 }) })), !['paid', 'cancelled'].includes(r.status) && (_jsx("button", { className: "btn-ghost p-1.5 text-amber-700", title: t('invoices.actions.cancel'), onClick: (e) => { e.stopPropagation(); cancel.mutate(r.id); }, children: _jsx(XCircle, { size: 14 }) })), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'invoice_number', header: t('invoices.exportCols.invoiceNumber'), value: (r) => r.invoice_number },
        { key: 'customer_name', header: t('invoices.exportCols.customer'), value: (r) => r.customer_name },
        { key: 'customer_email', header: t('invoices.exportCols.email'), value: (r) => r.customer_email },
        { key: 'customer_phone', header: t('invoices.exportCols.phone'), value: (r) => r.customer_phone },
        { key: 'issue_date', header: t('invoices.exportCols.issued'), value: (r) => r.issue_date },
        { key: 'due_date', header: t('invoices.exportCols.due'), value: (r) => r.due_date },
        { key: 'amount', header: t('invoices.exportCols.amount'), value: (r) => Number(r.amount) },
        { key: 'amount_paid', header: t('invoices.exportCols.paid'), value: (r) => Number(r.amount_paid) },
        { key: 'balance_due', header: t('invoices.exportCols.balance'), value: (r) => Number(r.balance_due) },
        { key: 'status', header: t('invoices.exportCols.status'), value: (r) => r.status_display },
        { key: 'is_overdue', header: t('invoices.exportCols.overdue'), value: (r) => (r.is_overdue ? t('common.yes') : t('common.no')) },
        { key: 'paid_at', header: t('invoices.exportCols.paidAt'), value: (r) => r.paid_at ?? '' },
        { key: 'description', header: t('invoices.exportCols.description'), value: (r) => r.description },
        { key: 'notes', header: t('invoices.exportCols.notes'), value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('invoices.title'), subtitle: t('invoices.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "invoices", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.invoices.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('invoices.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('invoices.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: FileText, title: t('invoices.emptyTitle') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('invoices.editModal') : t('invoices.newModal'), size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.customer_name || !form.invoice_number || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.invoiceNumber') }), _jsx("input", { className: "input font-mono", value: form.invoice_number ?? '', onChange: (e) => setForm({ ...form, invoice_number: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.status') }), _jsxs("select", { className: "input", value: form.status ?? 'draft', onChange: (e) => setForm({ ...form, status: e.target.value }), children: [_jsx("option", { value: "draft", children: t('invoices.statuses.draft') }), _jsx("option", { value: "sent", children: t('invoices.statuses.sent') }), _jsx("option", { value: "partially_paid", children: t('invoices.statuses.partially_paid') }), _jsx("option", { value: "paid", children: t('invoices.statuses.paid') }), _jsx("option", { value: "overdue", children: t('invoices.statuses.overdue') }), _jsx("option", { value: "cancelled", children: t('invoices.statuses.cancelled') })] })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('invoices.fields.customerName') }), _jsx("input", { className: "input", value: form.customer_name ?? '', onChange: (e) => setForm({ ...form, customer_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.email') }), _jsx("input", { type: "email", className: "input", value: form.customer_email ?? '', onChange: (e) => setForm({ ...form, customer_email: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.phone') }), _jsx("input", { className: "input", value: form.customer_phone ?? '', onChange: (e) => setForm({ ...form, customer_phone: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.issueDate') }), _jsx("input", { type: "date", className: "input", value: form.issue_date ?? '', onChange: (e) => setForm({ ...form, issue_date: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.dueDate') }), _jsx("input", { type: "date", className: "input", value: form.due_date ?? '', onChange: (e) => setForm({ ...form, due_date: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.amount') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount ?? '0', onChange: (e) => setForm({ ...form, amount: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.fields.amountPaid') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount_paid ?? '0', onChange: (e) => setForm({ ...form, amount_paid: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('invoices.fields.description') }), _jsx("textarea", { className: "input", rows: 2, value: form.description ?? '', onChange: (e) => setForm({ ...form, description: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('invoices.fields.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsxs(Modal, { open: !!paying, onClose: () => setPaying(null), title: t('invoices.payment.title', { number: paying?.invoice_number ?? '' }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setPaying(null), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !paymentAmount || Number(paymentAmount) <= 0 || recordPayment.isPending, onClick: () => recordPayment.mutate(), children: recordPayment.isPending ? t('common.saving') : t('invoices.payment.record') })] }), children: [_jsx("p", { className: "text-sm text-slate-500 mb-3", children: _jsx(Trans, { i18nKey: "invoices.payment.outstanding", values: { amount: formatMoney(paying?.balance_due ?? 0) }, components: { 1: _jsx("strong", {}) } }) }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('invoices.payment.amountReceived') }), _jsx("input", { type: "number", step: "0.01", autoFocus: true, className: "input", value: paymentAmount, onChange: (e) => setPaymentAmount(e.target.value) })] })] }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('invoices.deleteTitle'), message: t('invoices.deleteMessage', { number: toDelete?.invoice_number ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
