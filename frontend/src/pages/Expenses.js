import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
export function ExpensesPage() {
    const { t } = useTranslation();
    const [tab, setTab] = useState('expenses');
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('expenses.title'), subtitle: t('expenses.subtitle') }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx("div", { className: "flex gap-1", children: ['expenses', 'categories'].map((tabKey) => (_jsx("button", { onClick: () => setTab(tabKey), className: `px-3 py-1.5 rounded-md text-sm font-medium capitalize ${tab === tabKey ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: t(`expenses.tabs.${tabKey}`) }, tabKey))) }) }), tab === 'expenses' ? _jsx(ExpensesTab, {}) : _jsx(CategoriesTab, {})] })] }));
}
// ── Expenses tab ──────────────────────────────────────────────────────────
function ExpensesTab() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
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
    const emptyForm = {
        category: '', title: '', amount: '0',
        incurred_on: new Date().toISOString().slice(0, 10),
        payment_method: 'cash', supplier: null, reference: '', notes: '',
    };
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const [newCat, setNewCat] = useState({ open: false, name: '' });
    const save = useMutation({
        mutationFn: () => editing ? finance.expenses.update(editing.id, form) : finance.expenses.create(form),
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
    function openEdit(row) {
        setEditing(row);
        setForm(row);
        setNewCat({ open: false, name: '' });
        setOpen(true);
    }
    const columns = [
        { key: 'date', header: t('expenses.columns.date'), render: (r) => formatDate(r.incurred_on) },
        { key: 'title', header: t('expenses.columns.title'), render: (r) => _jsx("span", { className: "font-medium", children: r.title }) },
        { key: 'cat', header: t('expenses.columns.category'), render: (r) => _jsx("span", { className: "badge-gray", children: r.category_name }) },
        { key: 'amount', header: t('expenses.columns.amount'), align: 'right', render: (r) => _jsx("span", { className: "font-semibold", children: formatMoney(r.amount) }) },
        { key: 'pay', header: t('expenses.columns.payment'), render: (r) => r.payment_method_display },
        { key: 'sup', header: t('expenses.columns.supplier'), render: (r) => r.supplier_name ?? '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
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
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('expenses.list.searchPlaceholder') }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(ExportMenu, { filename: "expenses", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.expenses.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('expenses.list.new')] })] })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Wallet, title: t('expenses.list.emptyTitle'), description: t('expenses.list.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('expenses.list.editModal') : t('expenses.list.newModal'), size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.title || !form.amount || !form.category || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('expenses.fields.title') }), _jsx("input", { className: "input", value: form.title ?? '', onChange: (e) => setForm({ ...form, title: e.target.value }) })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("label", { className: "label", children: t('expenses.fields.category') }), !newCat.open && (_jsxs("button", { type: "button", onClick: () => setNewCat({ open: true, name: '' }), className: "text-xs font-medium text-brand-700 hover:text-brand-800 inline-flex items-center gap-0.5", children: [_jsx(Plus, { size: 12 }), " ", t('expenses.fields.new')] }))] }), newCat.open ? (_jsxs("div", { className: "flex gap-2", children: [_jsx("input", { autoFocus: true, className: "input flex-1", placeholder: t('expenses.fields.categoryNamePlaceholder'), value: newCat.name, onChange: (e) => setNewCat((s) => ({ ...s, name: e.target.value })), onKeyDown: (e) => {
                                                if (e.key === 'Enter' && newCat.name.trim() && !createCategory.isPending) {
                                                    e.preventDefault();
                                                    createCategory.mutate();
                                                }
                                                if (e.key === 'Escape') {
                                                    e.preventDefault();
                                                    setNewCat({ open: false, name: '' });
                                                }
                                            } }), _jsx("button", { type: "button", className: "btn-primary px-3", disabled: !newCat.name.trim() || createCategory.isPending, onClick: () => createCategory.mutate(), children: createCategory.isPending ? '…' : t('common.add') }), _jsx("button", { type: "button", className: "btn-secondary px-3", onClick: () => setNewCat({ open: false, name: '' }), children: t('common.cancel') })] })) : (_jsxs("select", { className: "input", value: form.category ?? '', onChange: (e) => setForm({ ...form, category: e.target.value }), children: [_jsx("option", { value: "", children: categories.data && categories.data.results.length === 0 ? t('expenses.fields.noneYet') : t('common.select') }), categories.data?.results.map((c) => _jsx("option", { value: c.id, children: c.name }, c.id))] }))] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.amount') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount ?? '0', onChange: (e) => setForm({ ...form, amount: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.date') }), _jsx("input", { type: "date", className: "input", value: form.incurred_on ?? '', onChange: (e) => setForm({ ...form, incurred_on: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.paymentMethod') }), _jsxs("select", { className: "input", value: form.payment_method ?? 'cash', onChange: (e) => setForm({ ...form, payment_method: e.target.value }), children: [_jsx("option", { value: "cash", children: t('expenses.fields.paymentMethods.cash') }), _jsx("option", { value: "mobile_money", children: t('expenses.fields.paymentMethods.mobile_money') }), _jsx("option", { value: "card", children: t('expenses.fields.paymentMethods.card') }), _jsx("option", { value: "bank_transfer", children: t('expenses.fields.paymentMethods.bank_transfer') })] })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('expenses.fields.supplierOptional') }), _jsxs("select", { className: "input", value: form.supplier ?? '', onChange: (e) => setForm({ ...form, supplier: e.target.value || null }), children: [_jsx("option", { value: "", children: t('common.none') }), suppliers.data?.results.map((s) => _jsx("option", { value: s.id, children: s.name }, s.id))] })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.reference') }), _jsx("input", { className: "input", value: form.reference ?? '', onChange: (e) => setForm({ ...form, reference: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('expenses.fields.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('expenses.list.deleteTitle'), message: t('expenses.list.deleteMessage', { title: toDelete?.title ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
// ── Categories tab ────────────────────────────────────────────────────────
function CategoriesTab() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['expense-cats'],
        fetcher: (p) => finance.expenseCategories.list(p),
        deleter: (id) => finance.expenseCategories.remove(id),
    });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState({ name: '', description: '', is_active: true });
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? finance.expenseCategories.update(editing.id, form) : finance.expenseCategories.create(form),
        onSuccess: () => {
            toast.success(editing ? t('expenses.categories.updated') : t('expenses.categories.created'));
            qc.invalidateQueries({ queryKey: ['expense-cats'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const columns = [
        { key: 'name', header: t('expenses.columns.name'), render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'desc', header: t('expenses.columns.description'), render: (r) => r.description || '—' },
        { key: 'status', header: t('expenses.columns.status'), render: (r) => r.is_active
                ? _jsx("span", { className: "badge-green", children: t('common.active') })
                : _jsx("span", { className: "badge-gray", children: t('common.off') })
        },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); setEditing(r); setForm(r); setOpen(true); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'name', header: t('expenses.exportCols.name'), value: (r) => r.name },
        { key: 'description', header: t('expenses.exportCols.description'), value: (r) => r.description },
        { key: 'is_active', header: t('expenses.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('expenses.categories.searchPlaceholder') }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(ExportMenu, { filename: "expense-categories", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.expenseCategories.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: () => { setEditing(null); setForm({ name: '', description: '', is_active: true }); setOpen(true); }, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('expenses.categories.new')] })] })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Folder, title: t('expenses.categories.emptyTitle') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('expenses.categories.editModal') : t('expenses.categories.newModal'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.name || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('expenses.fields.description') }), _jsx("textarea", { className: "input", rows: 2, value: form.description ?? '', onChange: (e) => setForm({ ...form, description: e.target.value }) })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('expenses.categories.deleteTitle'), message: t('expenses.categories.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
