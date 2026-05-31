import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Receipt } from 'lucide-react';
import { toast } from 'sonner';
import { finance } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
const emptyForm = {
    category: '',
    month: new Date(Date.now()).toISOString().slice(0, 7) + '-01',
    amount: '0',
    notes: '',
};
export function BudgetsPage() {
    const qc = useQueryClient();
    const list = useCrudList({
        queryKey: ['budgets'],
        fetcher: (p) => finance.budgets.list(p),
        deleter: (id) => finance.budgets.remove(id),
    });
    const categories = useQuery({
        queryKey: ['expense-cats-all'],
        queryFn: () => finance.expenseCategories.list({ page_size: 200 }),
    });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? finance.budgets.update(editing.id, form) : finance.budgets.create(form),
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
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'cat', header: 'Category', render: (r) => _jsx("span", { className: "font-medium", children: r.category_name }) },
        { key: 'month', header: 'Month', render: (r) => formatDate(r.month, { year: 'numeric', month: 'long' }) },
        { key: 'amount', header: 'Budgeted', align: 'right', render: (r) => _jsx("span", { className: "font-semibold", children: formatMoney(r.amount) }) },
        { key: 'notes', header: 'Notes', render: (r) => r.notes || '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'category', header: 'Category', value: (r) => r.category_name },
        { key: 'month', header: 'Month', value: (r) => r.month },
        { key: 'amount', header: 'Budgeted', value: (r) => Number(r.amount) },
        { key: 'notes', header: 'Notes', value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Budgets", subtitle: "Monthly spending caps per expense category", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "budgets", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.budgets.list(p)) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New budget"] })] }) }), _jsxs("div", { className: "card", children: [_jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Receipt, title: "No budgets defined", description: "Set monthly caps to monitor spending." }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? 'Edit budget' : 'New budget', footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !form.category || !form.amount || save.isPending, onClick: () => save.mutate(), children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Category" }), _jsxs("select", { className: "input", value: form.category ?? '', onChange: (e) => setForm({ ...form, category: e.target.value }), children: [_jsx("option", { value: "", children: "\u2014 Select \u2014" }), categories.data?.results.map((c) => _jsx("option", { value: c.id, children: c.name }, c.id))] })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Month (1st day)" }), _jsx("input", { type: "date", className: "input", value: form.month ?? '', onChange: (e) => setForm({ ...form, month: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Amount" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount ?? '0', onChange: (e) => setForm({ ...form, amount: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Notes" }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete budget?", message: "This will remove the budget entry.", confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
