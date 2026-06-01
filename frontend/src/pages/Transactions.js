import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
export function TransactionsPage() {
    const { t } = useTranslation();
    const [tab, setTab] = useState('transactions');
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('transactions.title'), subtitle: t('transactions.subtitle') }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx("div", { className: "flex gap-1", children: ['transactions', 'categories'].map((tabKey) => (_jsx("button", { onClick: () => setTab(tabKey), className: `px-3 py-1.5 rounded-md text-sm font-medium capitalize ${tab === tabKey ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: t(`transactions.tabs.${tabKey}`) }, tabKey))) }) }), tab === 'transactions' ? _jsx(TransactionsTab, {}) : _jsx(CategoriesTab, {})] })] }));
}
// ── Transactions tab ──────────────────────────────────────────────────────
function TransactionsTab() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const [directionFilter, setDirectionFilter] = useState('all');
    const list = useCrudList({
        queryKey: ['transactions', directionFilter],
        fetcher: (p) => finance.transactions.list(directionFilter === 'all' ? p : { ...p, direction: directionFilter }),
        deleter: (id) => finance.transactions.remove(id),
    });
    const categories = useQuery({
        queryKey: ['tx-cats-all'],
        queryFn: () => finance.transactionCategories.list({ page_size: 200 }),
    });
    const emptyForm = {
        direction: 'expense',
        category: '', title: '', amount: '0',
        occurred_on: new Date().toISOString().slice(0, 10),
        payment_method: 'cash', counterparty: '', reference: '', notes: '',
    };
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const [newCat, setNewCat] = useState({ open: false, name: '' });
    const matchingCategories = (categories.data?.results ?? []).filter((c) => c.direction === form.direction);
    const save = useMutation({
        mutationFn: () => editing ? finance.transactions.update(editing.id, form) : finance.transactions.create(form),
        onSuccess: () => {
            toast.success(editing ? t('transactions.list.updated') : t('transactions.list.created'));
            qc.invalidateQueries({ queryKey: ['transactions'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const createCategory = useMutation({
        mutationFn: () => finance.transactionCategories.create({
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
    function openCreate(direction = 'expense') {
        setEditing(null);
        const firstCat = (categories.data?.results ?? []).find((c) => c.direction === direction);
        setForm({ ...emptyForm, direction, category: firstCat?.id ?? '' });
        setNewCat({ open: false, name: '' });
        setOpen(true);
    }
    function openEdit(row) {
        setEditing(row);
        setForm(row);
        setNewCat({ open: false, name: '' });
        setOpen(true);
    }
    function setDirection(direction) {
        const firstCat = (categories.data?.results ?? []).find((c) => c.direction === direction);
        setForm((f) => ({ ...f, direction, category: firstCat?.id ?? '' }));
    }
    const columns = [
        { key: 'date', header: t('transactions.columns.date'), render: (r) => formatDate(r.occurred_on) },
        { key: 'dir', header: t('transactions.columns.direction'), render: (r) => (r.direction === 'income'
                ? _jsx("span", { className: "badge-green", children: t('transactions.directions.income') })
                : _jsx("span", { className: "badge-gray", children: t('transactions.directions.expense') })) },
        { key: 'title', header: t('transactions.columns.title'), render: (r) => _jsx("span", { className: "font-medium", children: r.title }) },
        { key: 'cat', header: t('transactions.columns.category'), render: (r) => _jsx("span", { className: "badge-gray", children: r.category_name }) },
        { key: 'amount', header: t('transactions.columns.amount'), align: 'right', render: (r) => (_jsxs("span", { className: `font-semibold ${r.direction === 'income' ? 'text-emerald-600' : 'text-slate-900'}`, children: [r.direction === 'income' ? '+' : '−', formatMoney(r.amount)] })) },
        { key: 'pay', header: t('transactions.columns.payment'), render: (r) => r.payment_method_display },
        { key: 'party', header: t('transactions.columns.counterparty'), render: (r) => r.counterparty || '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
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
    const directionTabs = ['all', 'income', 'expense'];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2 flex-wrap", children: [_jsxs("div", { className: "flex items-center gap-2 flex-wrap", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('transactions.list.searchPlaceholder') }), _jsx("div", { className: "flex gap-1", children: directionTabs.map((d) => (_jsx("button", { onClick: () => setDirectionFilter(d), className: `px-2.5 py-1 rounded-md text-xs font-medium ${directionFilter === d ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: t(`transactions.filters.${d}`) }, d))) })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(ExportMenu, { filename: "transactions", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.transactions.list(p), {
                                    ...(list.search ? { search: list.search } : {}),
                                    ...(directionFilter !== 'all' ? { direction: directionFilter } : {}),
                                }) }), _jsxs("button", { onClick: () => openCreate('income'), className: "btn-secondary", children: [_jsx(Plus, { size: 16 }), " ", t('transactions.list.newIncome')] }), _jsxs("button", { onClick: () => openCreate('expense'), className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('transactions.list.newExpense')] })] })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: ArrowLeftRight, title: t('transactions.list.emptyTitle'), description: t('transactions.list.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('transactions.list.editModal') : t('transactions.list.newModal'), size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.title || !form.amount || !form.category || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('transactions.fields.direction') }), _jsx("div", { className: "flex gap-2", children: ['income', 'expense'].map((d) => (_jsx("button", { type: "button", onClick: () => setDirection(d), className: `flex-1 px-3 py-2 rounded-md text-sm font-medium border ${form.direction === d
                                            ? d === 'income'
                                                ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                                                : 'border-brand-500 bg-brand-50 text-brand-700'
                                            : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`, children: t(`transactions.directions.${d}`) }, d))) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('transactions.fields.title') }), _jsx("input", { className: "input", value: form.title ?? '', onChange: (e) => setForm({ ...form, title: e.target.value }) })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("label", { className: "label", children: t('transactions.fields.category') }), !newCat.open && (_jsxs("button", { type: "button", onClick: () => setNewCat({ open: true, name: '' }), className: "text-xs font-medium text-brand-700 hover:text-brand-800 inline-flex items-center gap-0.5", children: [_jsx(Plus, { size: 12 }), " ", t('transactions.fields.new')] }))] }), newCat.open ? (_jsxs("div", { className: "flex gap-2", children: [_jsx("input", { autoFocus: true, className: "input flex-1", placeholder: t('transactions.fields.categoryNamePlaceholder'), value: newCat.name, onChange: (e) => setNewCat((s) => ({ ...s, name: e.target.value })), onKeyDown: (e) => {
                                                if (e.key === 'Enter' && newCat.name.trim() && !createCategory.isPending) {
                                                    e.preventDefault();
                                                    createCategory.mutate();
                                                }
                                                if (e.key === 'Escape') {
                                                    e.preventDefault();
                                                    setNewCat({ open: false, name: '' });
                                                }
                                            } }), _jsx("button", { type: "button", className: "btn-primary px-3", disabled: !newCat.name.trim() || createCategory.isPending, onClick: () => createCategory.mutate(), children: createCategory.isPending ? '…' : t('common.add') }), _jsx("button", { type: "button", className: "btn-secondary px-3", onClick: () => setNewCat({ open: false, name: '' }), children: t('common.cancel') })] })) : (_jsxs("select", { className: "input", value: form.category ?? '', onChange: (e) => setForm({ ...form, category: e.target.value }), children: [_jsx("option", { value: "", children: matchingCategories.length === 0 ? t('transactions.fields.noneYet') : t('common.select') }), matchingCategories.map((c) => _jsx("option", { value: c.id, children: c.name }, c.id))] }))] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.amount') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.amount ?? '0', onChange: (e) => setForm({ ...form, amount: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.date') }), _jsx("input", { type: "date", className: "input", value: form.occurred_on ?? '', onChange: (e) => setForm({ ...form, occurred_on: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.paymentMethod') }), _jsxs("select", { className: "input", value: form.payment_method ?? 'cash', onChange: (e) => setForm({ ...form, payment_method: e.target.value }), children: [_jsx("option", { value: "cash", children: t('transactions.fields.paymentMethods.cash') }), _jsx("option", { value: "mobile_money", children: t('transactions.fields.paymentMethods.mobile_money') }), _jsx("option", { value: "card", children: t('transactions.fields.paymentMethods.card') }), _jsx("option", { value: "bank_transfer", children: t('transactions.fields.paymentMethods.bank_transfer') })] })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: form.direction === 'income'
                                        ? t('transactions.fields.customerOptional')
                                        : t('transactions.fields.supplierOptional') }), _jsx("input", { className: "input", value: form.counterparty ?? '', onChange: (e) => setForm({ ...form, counterparty: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.reference') }), _jsx("input", { className: "input", value: form.reference ?? '', onChange: (e) => setForm({ ...form, reference: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('transactions.fields.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('transactions.list.deleteTitle'), message: t('transactions.list.deleteMessage', { title: toDelete?.title ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
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
        queryKey: ['tx-cats'],
        fetcher: (p) => finance.transactionCategories.list(p),
        deleter: (id) => finance.transactionCategories.remove(id),
    });
    const emptyForm = { name: '', direction: 'expense', description: '', is_active: true };
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? finance.transactionCategories.update(editing.id, form) : finance.transactionCategories.create(form),
        onSuccess: () => {
            toast.success(editing ? t('transactions.categories.updated') : t('transactions.categories.created'));
            qc.invalidateQueries({ queryKey: ['tx-cats'] });
            qc.invalidateQueries({ queryKey: ['tx-cats-all'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const columns = [
        { key: 'name', header: t('transactions.columns.name'), render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'dir', header: t('transactions.columns.direction'), render: (r) => (r.direction === 'income'
                ? _jsx("span", { className: "badge-green", children: t('transactions.directions.income') })
                : _jsx("span", { className: "badge-gray", children: t('transactions.directions.expense') })) },
        { key: 'desc', header: t('transactions.columns.description'), render: (r) => r.description || '—' },
        { key: 'status', header: t('transactions.columns.status'), render: (r) => r.is_active
                ? _jsx("span", { className: "badge-green", children: t('common.active') })
                : _jsx("span", { className: "badge-gray", children: t('common.off') })
        },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); setEditing(r); setForm(r); setOpen(true); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'name', header: t('transactions.exportCols.name'), value: (r) => r.name },
        { key: 'direction', header: t('transactions.exportCols.direction'), value: (r) => r.direction_display },
        { key: 'description', header: t('transactions.exportCols.description'), value: (r) => r.description },
        { key: 'is_active', header: t('transactions.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('transactions.categories.searchPlaceholder') }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(ExportMenu, { filename: "transaction-categories", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.transactionCategories.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: () => { setEditing(null); setForm(emptyForm); setOpen(true); }, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('transactions.categories.new')] })] })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Folder, title: t('transactions.categories.emptyTitle') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('transactions.categories.editModal') : t('transactions.categories.newModal'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.name || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.direction') }), _jsx("div", { className: "flex gap-2", children: ['income', 'expense'].map((d) => (_jsx("button", { type: "button", onClick: () => setForm({ ...form, direction: d }), className: `flex-1 px-3 py-2 rounded-md text-sm font-medium border ${form.direction === d
                                            ? d === 'income'
                                                ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                                                : 'border-brand-500 bg-brand-50 text-brand-700'
                                            : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`, children: t(`transactions.directions.${d}`) }, d))) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('transactions.fields.description') }), _jsx("textarea", { className: "input", rows: 2, value: form.description ?? '', onChange: (e) => setForm({ ...form, description: e.target.value }) })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('transactions.categories.deleteTitle'), message: t('transactions.categories.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
