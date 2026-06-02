import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Building, PackageOpen, RotateCcw } from 'lucide-react';
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
const CATEGORY_KEYS = [
    'equipment',
    'furniture',
    'vehicle',
    'electronics',
    'fit_out',
    'other',
];
const emptyForm = {
    name: '',
    category: 'equipment',
    purchase_date: new Date().toISOString().slice(0, 10),
    purchase_cost: '0',
    useful_life_months: null,
    supplier: null,
    reference: '',
    notes: '',
    record_as_expense: false,
    expense_category: '',
};
export function AssetsPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['assets'],
        fetcher: (p) => finance.assets.list(p),
        deleter: (id) => finance.assets.remove(id),
    });
    const suppliers = useQuery({
        queryKey: ['suppliers-for-assets'],
        queryFn: () => catalog.suppliers.list({ page_size: 200, is_active: true }),
    });
    const expenseCategories = useQuery({
        queryKey: ['expense-cats-for-assets'],
        queryFn: () => finance.expenseCategories.list({ page_size: 200 }),
    });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => {
            if (editing) {
                // Only send editable fields on update — strip the create-only auto-expense flags.
                const { record_as_expense: _r, expense_category: _e, ...patch } = form;
                return finance.assets.update(editing.id, patch);
            }
            return finance.assets.create(form);
        },
        onSuccess: () => {
            toast.success(editing ? t('assets.updated') : t('assets.created'));
            qc.invalidateQueries({ queryKey: ['assets'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const dispose = useMutation({
        mutationFn: (id) => finance.assets.dispose(id),
        onSuccess: () => {
            toast.success(t('assets.disposed'));
            qc.invalidateQueries({ queryKey: ['assets'] });
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const reactivate = useMutation({
        mutationFn: (id) => finance.assets.reactivate(id),
        onSuccess: () => {
            toast.success(t('assets.reactivated'));
            qc.invalidateQueries({ queryKey: ['assets'] });
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() {
        setEditing(null);
        setForm(emptyForm);
        setOpen(true);
    }
    function openEdit(row) {
        setEditing(row);
        setForm({
            name: row.name,
            category: row.category,
            purchase_date: row.purchase_date,
            purchase_cost: row.purchase_cost,
            useful_life_months: row.useful_life_months,
            supplier: row.supplier,
            reference: row.reference,
            notes: row.notes,
            status: row.status,
        });
        setOpen(true);
    }
    const columns = [
        {
            key: 'name',
            header: t('assets.columns.name'),
            render: (r) => (_jsxs("div", { children: [_jsx("div", { className: "font-medium", children: r.name }), r.reference && (_jsx("div", { className: "text-xs text-slate-500", children: r.reference }))] })),
        },
        {
            key: 'category',
            header: t('assets.columns.category'),
            render: (r) => t(`assets.categories.${r.category}`),
        },
        {
            key: 'purchase_date',
            header: t('assets.columns.purchased'),
            render: (r) => formatDate(r.purchase_date),
        },
        {
            key: 'purchase_cost',
            header: t('assets.columns.cost'),
            align: 'right',
            render: (r) => formatMoney(r.purchase_cost),
        },
        {
            key: 'life',
            header: t('assets.columns.usefulLife'),
            align: 'right',
            render: (r) => r.useful_life_months
                ? t('assets.monthsValue', { count: r.useful_life_months })
                : '—',
        },
        {
            key: 'carrying',
            header: t('assets.columns.carryingValue'),
            align: 'right',
            render: (r) => (_jsx("span", { className: "font-semibold", children: formatMoney(r.carrying_value) })),
        },
        {
            key: 'status',
            header: t('assets.columns.status'),
            render: (r) => r.status === 'active' ? (_jsx("span", { className: "badge-green", children: t('assets.statuses.active') })) : (_jsx("span", { className: "badge-gray", children: t('assets.statuses.disposed') })),
        },
        {
            key: 'actions',
            header: '',
            align: 'right',
            render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [r.status === 'active' ? (_jsx("button", { className: "btn-ghost p-1.5", title: t('assets.actions.dispose'), onClick: (e) => {
                            e.stopPropagation();
                            dispose.mutate(r.id);
                        }, children: _jsx(PackageOpen, { size: 14 }) })) : (_jsx("button", { className: "btn-ghost p-1.5", title: t('assets.actions.reactivate'), onClick: (e) => {
                            e.stopPropagation();
                            reactivate.mutate(r.id);
                        }, children: _jsx(RotateCcw, { size: 14 }) })), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => {
                            e.stopPropagation();
                            openEdit(r);
                        }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => {
                            e.stopPropagation();
                            setToDelete(r);
                        }, children: _jsx(Trash2, { size: 14 }) })] })),
        },
    ];
    const exportColumns = [
        { key: 'name', header: t('assets.exportCols.name'), value: (r) => r.name },
        {
            key: 'category',
            header: t('assets.exportCols.category'),
            value: (r) => t(`assets.categories.${r.category}`),
        },
        {
            key: 'purchase_date',
            header: t('assets.exportCols.purchased'),
            value: (r) => r.purchase_date,
        },
        {
            key: 'purchase_cost',
            header: t('assets.exportCols.cost'),
            value: (r) => Number(r.purchase_cost),
        },
        {
            key: 'useful_life_months',
            header: t('assets.exportCols.usefulLifeMonths'),
            value: (r) => r.useful_life_months ?? '',
        },
        {
            key: 'accumulated_depreciation',
            header: t('assets.exportCols.accumulatedDepreciation'),
            value: (r) => Number(r.accumulated_depreciation),
        },
        {
            key: 'carrying_value',
            header: t('assets.exportCols.carryingValue'),
            value: (r) => Number(r.carrying_value),
        },
        {
            key: 'supplier',
            header: t('assets.exportCols.supplier'),
            value: (r) => r.supplier_name ?? '',
        },
        {
            key: 'reference',
            header: t('assets.exportCols.reference'),
            value: (r) => r.reference,
        },
        {
            key: 'status',
            header: t('assets.exportCols.status'),
            value: (r) => t(`assets.statuses.${r.status}`),
        },
        { key: 'notes', header: t('assets.exportCols.notes'), value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('assets.title'), subtitle: t('assets.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "assets", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.assets.list(p)) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('assets.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "p-3 border-b border-slate-200", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('assets.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Building, title: t('assets.emptyTitle'), description: t('assets.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('assets.editModal') : t('assets.newModal'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.name ||
                                !form.purchase_cost ||
                                Number(form.purchase_cost) <= 0 ||
                                save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('assets.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }), placeholder: t('assets.fields.namePlaceholder') })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('assets.fields.category') }), _jsx("select", { className: "input", value: form.category ?? 'equipment', onChange: (e) => setForm({ ...form, category: e.target.value }), children: CATEGORY_KEYS.map((k) => (_jsx("option", { value: k, children: t(`assets.categories.${k}`) }, k))) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('assets.fields.purchaseDate') }), _jsx("input", { type: "date", className: "input", value: form.purchase_date ?? '', onChange: (e) => setForm({ ...form, purchase_date: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('assets.fields.purchaseCost') }), _jsx("input", { type: "number", step: "0.01", min: "0", className: "input", value: form.purchase_cost ?? '0', onChange: (e) => setForm({ ...form, purchase_cost: e.target.value }) })] }), _jsxs("div", { children: [_jsxs("label", { className: "label", children: [t('assets.fields.usefulLifeMonths'), ' ', _jsxs("span", { className: "text-slate-400", children: ["(", t('common.optional'), ")"] })] }), _jsx("input", { type: "number", min: "0", step: "1", className: "input", value: form.useful_life_months ?? '', onChange: (e) => setForm({
                                        ...form,
                                        useful_life_months: e.target.value === '' ? null : Number(e.target.value),
                                    }), placeholder: t('assets.fields.usefulLifePlaceholder') })] }), _jsxs("div", { children: [_jsxs("label", { className: "label", children: [t('assets.fields.supplier'), ' ', _jsxs("span", { className: "text-slate-400", children: ["(", t('common.optional'), ")"] })] }), _jsxs("select", { className: "input", value: form.supplier ?? '', onChange: (e) => setForm({ ...form, supplier: e.target.value || null }), children: [_jsx("option", { value: "", children: t('common.none') }), suppliers.data?.results.map((s) => (_jsx("option", { value: s.id, children: s.name }, s.id)))] })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsxs("label", { className: "label", children: [t('assets.fields.reference'), ' ', _jsxs("span", { className: "text-slate-400", children: ["(", t('common.optional'), ")"] })] }), _jsx("input", { className: "input", value: form.reference ?? '', onChange: (e) => setForm({ ...form, reference: e.target.value }), placeholder: t('assets.fields.referencePlaceholder') })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('common.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] }), !editing && (_jsxs("div", { className: "sm:col-span-2 border-t border-slate-200 pt-3", children: [_jsxs("label", { className: "flex items-center gap-2 text-sm font-medium", children: [_jsx("input", { type: "checkbox", checked: !!form.record_as_expense, onChange: (e) => setForm({ ...form, record_as_expense: e.target.checked }) }), t('assets.fields.recordAsExpense')] }), _jsx("p", { className: "text-xs text-slate-500 mt-1", children: t('assets.fields.recordAsExpenseHint') }), form.record_as_expense && (_jsxs("div", { className: "mt-2", children: [_jsx("label", { className: "label", children: t('assets.fields.expenseCategory') }), _jsxs("select", { className: "input", value: form.expense_category ?? '', onChange: (e) => setForm({ ...form, expense_category: e.target.value }), children: [_jsx("option", { value: "", children: t('common.select') }), expenseCategories.data?.results.map((c) => (_jsx("option", { value: c.id, children: c.name }, c.id)))] })] }))] }))] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('assets.deleteTitle'), message: t('assets.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (toDelete)
                        list.deleteMutation.mutate(toDelete.id, {
                            onSettled: () => setToDelete(null),
                        });
                } })] }));
}
