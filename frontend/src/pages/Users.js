import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Users2, ShieldCheck, ShieldOff } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
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
    const { t } = useTranslation();
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
            toast.success(editing ? t('users.updated') : t('users.created'));
            qc.invalidateQueries({ queryKey: ['users'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const toggle = useMutation({
        mutationFn: (u) => u.is_active ? usersApi.deactivate(u.id) : usersApi.activate(u.id),
        onSuccess: () => { toast.success(t('common.updated')); qc.invalidateQueries({ queryKey: ['users'] }); },
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
        { key: 'name', header: t('users.columns.name'), render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.full_name }), _jsx("p", { className: "text-xs text-slate-500", children: r.email })] })) },
        { key: 'phone', header: t('users.columns.phone'), render: (r) => r.phone || '—' },
        { key: 'role', header: t('users.columns.role'), render: (r) => _jsx("span", { className: ROLE_BADGE[r.role] ?? 'badge-gray', children: r.role }) },
        { key: 'status', header: t('users.columns.status'), render: (r) => r.is_active
                ? _jsx("span", { className: "badge-green", children: t('common.active') })
                : _jsx("span", { className: "badge-gray", children: t('common.inactive') })
        },
        { key: 'joined', header: t('users.columns.joined'), render: (r) => formatDate(r.date_joined) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5", title: r.is_active ? t('users.actions.deactivate') : t('users.actions.activate'), onClick: (e) => { e.stopPropagation(); toggle.mutate(r); }, children: r.is_active ? _jsx(ShieldOff, { size: 14 }) : _jsx(ShieldCheck, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'full_name', header: t('users.exportCols.name'), value: (r) => r.full_name },
        { key: 'email', header: t('users.exportCols.email'), value: (r) => r.email },
        { key: 'phone', header: t('users.exportCols.phone'), value: (r) => r.phone },
        { key: 'role', header: t('users.exportCols.role'), value: (r) => r.role },
        { key: 'is_active', header: t('users.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
        { key: 'date_joined', header: t('users.exportCols.joined'), value: (r) => r.date_joined },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('users.title'), subtitle: t('users.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "staff", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => usersApi.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('users.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('users.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Users2, title: t('users.emptyTitle') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('users.editModal', { name: editing.full_name }) : t('users.newModal'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.email || !form.full_name || (!editing && !form.password) || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('users.fields.fullName') }), _jsx("input", { className: "input", value: form.full_name, onChange: (e) => setForm({ ...form, full_name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('users.fields.email') }), _jsx("input", { type: "email", className: "input", value: form.email, onChange: (e) => setForm({ ...form, email: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('users.fields.phone') }), _jsx("input", { className: "input", value: form.phone, onChange: (e) => setForm({ ...form, phone: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('users.fields.role') }), _jsx("select", { className: "input", value: form.role, onChange: (e) => setForm({ ...form, role: e.target.value }), children: roles.data?.map((r) => _jsx("option", { value: r.value, children: r.label }, r.value)) })] }), !editing && (_jsxs("div", { children: [_jsx("label", { className: "label", children: t('users.fields.password') }), _jsx("input", { type: "password", className: "input", value: form.password, onChange: (e) => setForm({ ...form, password: e.target.value }), autoComplete: "new-password" })] })), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-user", type: "checkbox", checked: form.is_active, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-user", className: "text-sm", children: t('users.fields.active') })] })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('users.deleteTitle'), message: t('users.deleteMessage', { name: toDelete?.full_name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => { if (toDelete)
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); } })] }));
}
