import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Users2, ShieldCheck, ShieldOff } from 'lucide-react';
import { toast } from 'sonner';
import { auth as authApi, users as usersApi } from '@/api/endpoints';
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
import { formatDate } from '@/lib/format';
const ROLE_BADGE = {
    admin: 'badge-red', manager: 'badge-blue', accountant: 'badge-yellow',
    cashier: 'badge-green', staff: 'badge-gray',
};
const emptyForm = {
    email: '', full_name: '', phone: '', role: 'staff', is_active: true, password: '',
};
export function UsersPage() {
    const qc = useQueryClient();
    const list = useCrudList({
        queryKey: ['users'],
        fetcher: (p) => usersApi.list(p),
        deleter: (id) => usersApi.remove(id),
    });
    const roles = useQuery({ queryKey: ['roles'], queryFn: authApi.roles });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const save = useMutation({
        mutationFn: () => {
            if (editing) {
                const { password: _pw, ...rest } = form;
                return usersApi.update(editing.id, rest);
            }
            return usersApi.create(form);
        },
        onSuccess: () => {
            toast.success(editing ? 'User updated.' : 'User created.');
            qc.invalidateQueries({ queryKey: ['users'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const toggle = useMutation({
        mutationFn: (u) => u.is_active ? usersApi.deactivate(u.id) : usersApi.activate(u.id),
        onSuccess: () => { toast.success('Updated.'); qc.invalidateQueries({ queryKey: ['users'] }); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() { setEditing(null); setForm(emptyForm); setOpen(true); }
    function openEdit(u) {
        setEditing(u);
        setForm({
            email: u.email, full_name: u.full_name, phone: u.phone,
            role: u.role, is_active: u.is_active, password: '',
        });
        setOpen(true);
    }
    const columns = [
        { key: 'name', header: 'Name', render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.full_name }), _jsx("p", { className: "text-xs text-slate-500", children: r.email })] })) },
        { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
        { key: 'role', header: 'Role', render: (r) => _jsx("span", { className: ROLE_BADGE[r.role] ?? 'badge-gray', children: r.role }) },
        { key: 'status', header: 'Status', render: (r) => r.is_active ? _jsx("span", { className: "badge-green", children: "Active" }) : _jsx("span", { className: "badge-gray", children: "Inactive" })
        },
        { key: 'joined', header: 'Joined', render: (r) => formatDate(r.date_joined) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", title: r.is_active ? 'Deactivate' : 'Activate', onClick: (e) => { e.stopPropagation(); toggle.mutate(r); }, children: r.is_active ? _jsx(ShieldOff, { size: 14 }) : _jsx(ShieldCheck, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'full_name', header: 'Name', value: (r) => r.full_name },
        { key: 'email', header: 'Email', value: (r) => r.email },
        { key: 'phone', header: 'Phone', value: (r) => r.phone },
        { key: 'role', header: 'Role', value: (r) => r.role },
        { key: 'is_active', header: 'Active', value: (r) => (r.is_active ? 'yes' : 'no') },
        { key: 'date_joined', header: 'Joined', value: (r) => r.date_joined },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Staff", subtitle: "Internal users with role-based access", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "staff", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => usersApi.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New user"] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search by name or email\u2026" }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Users2, title: "No staff accounts yet" }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? `Edit ${editing.full_name}` : 'New user', footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !form.email || !form.full_name || (!editing && !form.password) || save.isPending, onClick: () => save.mutate(), children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Full name" }), _jsx("input", { className: "input", value: form.full_name, onChange: (e) => setForm({ ...form, full_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Email" }), _jsx("input", { type: "email", className: "input", value: form.email, onChange: (e) => setForm({ ...form, email: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Phone" }), _jsx("input", { className: "input", value: form.phone, onChange: (e) => setForm({ ...form, phone: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Role" }), _jsx("select", { className: "input", value: form.role, onChange: (e) => setForm({ ...form, role: e.target.value }), children: roles.data?.map((r) => _jsx("option", { value: r.value, children: r.label }, r.value)) })] }), !editing && (_jsxs("div", { children: [_jsx("label", { className: "label", children: "Password" }), _jsx("input", { type: "password", className: "input", value: form.password, onChange: (e) => setForm({ ...form, password: e.target.value }), autoComplete: "new-password" })] })), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-user", type: "checkbox", checked: form.is_active, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-user", className: "text-sm", children: "Active" })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete user?", message: `Permanently remove "${toDelete?.full_name}"?`, confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
