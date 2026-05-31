import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Building2 } from 'lucide-react';
import { toast } from 'sonner';
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
            toast.success(editing ? 'Supplier updated.' : 'Supplier created.');
            qc.invalidateQueries({ queryKey: ['suppliers'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'name', header: 'Name', render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'contact', header: 'Contact', render: (r) => r.contact_name || '—' },
        { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
        { key: 'email', header: 'Email', render: (r) => r.email || '—' },
        { key: 'active', header: 'Status', render: (r) => (r.is_active ? _jsx("span", { className: "badge-green", children: "Active" }) : _jsx("span", { className: "badge-gray", children: "Inactive" })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'name', header: 'Name', value: (r) => r.name },
        { key: 'contact_name', header: 'Contact', value: (r) => r.contact_name },
        { key: 'phone', header: 'Phone', value: (r) => r.phone },
        { key: 'email', header: 'Email', value: (r) => r.email },
        { key: 'address', header: 'Address', value: (r) => r.address },
        { key: 'notes', header: 'Notes', value: (r) => r.notes },
        { key: 'is_active', header: 'Active', value: (r) => (r.is_active ? 'yes' : 'no') },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Suppliers", subtitle: "Vendors for raw materials and other supplies", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "suppliers", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => catalog.suppliers.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New supplier"] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search suppliers\u2026" }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Building2, title: "No suppliers yet", description: "Add the vendors you buy from." }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? 'Edit supplier' : 'New supplier', footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", onClick: () => save.mutate(), disabled: save.isPending || !form.name, children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Company name" }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Contact person" }), _jsx("input", { className: "input", value: form.contact_name ?? '', onChange: (e) => setForm({ ...form, contact_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Phone" }), _jsx("input", { className: "input", value: form.phone ?? '', onChange: (e) => setForm({ ...form, phone: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Email" }), _jsx("input", { type: "email", className: "input", value: form.email ?? '', onChange: (e) => setForm({ ...form, email: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Address" }), _jsx("textarea", { className: "input", rows: 2, value: form.address ?? '', onChange: (e) => setForm({ ...form, address: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Notes" }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active", className: "text-sm", children: "Active" })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete supplier?", message: `Permanently remove "${toDelete?.name}"? This cannot be undone.`, confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
