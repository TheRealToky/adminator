import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Building2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { catalog } from '@/api/endpoints';
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
const empty = {
    name: '', contact_name: '', phone: '', email: '', address: '', notes: '', is_active: true,
};
export function SuppliersPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['suppliers'],
        fetcher: (p) => catalog.suppliers.list(p),
        deleter: (id) => catalog.suppliers.remove(id),
    });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(empty);
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? catalog.suppliers.update(editing.id, form) : catalog.suppliers.create(form),
        onSuccess: () => {
            toast.success(editing ? t('suppliers.updated') : t('suppliers.created'));
            qc.invalidateQueries({ queryKey: ['suppliers'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'name', header: t('suppliers.columns.name'), render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'contact', header: t('suppliers.columns.contact'), render: (r) => r.contact_name || '—' },
        { key: 'phone', header: t('suppliers.columns.phone'), render: (r) => r.phone || '—' },
        { key: 'email', header: t('suppliers.columns.email'), render: (r) => r.email || '—' },
        { key: 'active', header: t('suppliers.columns.status'), render: (r) => (r.is_active
                ? _jsx("span", { className: "badge-green", children: t('common.active') })
                : _jsx("span", { className: "badge-gray", children: t('common.inactive') })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'name', header: t('suppliers.exportCols.name'), value: (r) => r.name },
        { key: 'contact_name', header: t('suppliers.exportCols.contact'), value: (r) => r.contact_name },
        { key: 'phone', header: t('suppliers.exportCols.phone'), value: (r) => r.phone },
        { key: 'email', header: t('suppliers.exportCols.email'), value: (r) => r.email },
        { key: 'address', header: t('suppliers.exportCols.address'), value: (r) => r.address },
        { key: 'notes', header: t('suppliers.exportCols.notes'), value: (r) => r.notes },
        { key: 'is_active', header: t('suppliers.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('suppliers.title'), subtitle: t('suppliers.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "suppliers", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => catalog.suppliers.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('suppliers.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('suppliers.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Building2, title: t('suppliers.emptyTitle'), description: t('suppliers.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('suppliers.edit') : t('suppliers.new'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", onClick: () => save.mutate(), disabled: save.isPending || !form.name, children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('suppliers.fields.companyName') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('suppliers.fields.contact') }), _jsx("input", { className: "input", value: form.contact_name ?? '', onChange: (e) => setForm({ ...form, contact_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('suppliers.fields.phone') }), _jsx("input", { className: "input", value: form.phone ?? '', onChange: (e) => setForm({ ...form, phone: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('suppliers.fields.email') }), _jsx("input", { type: "email", className: "input", value: form.email ?? '', onChange: (e) => setForm({ ...form, email: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('suppliers.fields.address') }), _jsx("textarea", { className: "input", rows: 2, value: form.address ?? '', onChange: (e) => setForm({ ...form, address: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('suppliers.fields.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active", className: "text-sm", children: t('suppliers.fields.active') })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('suppliers.deleteTitle'), message: t('suppliers.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
