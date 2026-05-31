import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Users2, ShieldCheck, ShieldOff } from 'lucide-react';
import { toast } from 'sonner';

import { auth as authApi, users as usersApi } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatDate } from '@/lib/format';
import type { User } from '@/api/types';

const ROLE_BADGE: Record<string, string> = {
  admin: 'badge-red', manager: 'badge-blue', accountant: 'badge-yellow',
  cashier: 'badge-green', staff: 'badge-gray',
};

interface FormState {
  email: string;
  full_name: string;
  phone: string;
  role: User['role'];
  is_active: boolean;
  password: string;
}

const emptyForm: FormState = {
  email: '', full_name: '', phone: '', role: 'staff', is_active: true, password: '',
};

export function UsersPage() {
  const qc = useQueryClient();
  const list = useCrudList<User>({
    queryKey: ['users'],
    fetcher: (p) => usersApi.list(p),
    deleter: (id) => usersApi.remove(id),
  });
  const roles = useQuery({ queryKey: ['roles'], queryFn: authApi.roles });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [toDelete, setToDelete] = useState<User | null>(null);

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
    mutationFn: (u: User) => u.is_active ? usersApi.deactivate(u.id) : usersApi.activate(u.id),
    onSuccess: () => { toast.success('Updated.'); qc.invalidateQueries({ queryKey: ['users'] }); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(emptyForm); setOpen(true); }
  function openEdit(u: User) {
    setEditing(u);
    setForm({
      email: u.email, full_name: u.full_name, phone: u.phone,
      role: u.role, is_active: u.is_active, password: '',
    });
    setOpen(true);
  }

  const columns: Column<User>[] = [
    { key: 'name', header: 'Name', render: (r) => (
      <div>
        <p className="font-medium">{r.full_name}</p>
        <p className="text-xs text-slate-500">{r.email}</p>
      </div>
    )},
    { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
    { key: 'role', header: 'Role', render: (r) => <span className={ROLE_BADGE[r.role] ?? 'badge-gray'}>{r.role}</span> },
    { key: 'status', header: 'Status', render: (r) =>
      r.is_active ? <span className="badge-green">Active</span> : <span className="badge-gray">Inactive</span>
    },
    { key: 'joined', header: 'Joined', render: (r) => formatDate(r.date_joined) },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5"
          title={r.is_active ? 'Deactivate' : 'Activate'}
          onClick={(e) => { e.stopPropagation(); toggle.mutate(r); }}
        >
          {r.is_active ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
        </button>
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  return (
    <>
      <PageHeader
        title="Staff"
        subtitle="Internal users with role-based access"
        actions={<button onClick={openCreate} className="btn-primary"><Plus size={16} /> New user</button>}
      />
      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search by name or email…" />
        </div>
        <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
          empty={<EmptyState icon={Users2} title="No staff accounts yet" />} />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? `Edit ${editing.full_name}` : 'New user'}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!form.email || !form.full_name || (!editing && !form.password) || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">Full name</label>
            <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as User['role'] })}
            >
              {roles.data?.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          {!editing && (
            <div>
              <label className="label">Password</label>
              <input
                type="password" className="input" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                autoComplete="new-password"
              />
            </div>
          )}
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-user" type="checkbox" checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-user" className="text-sm">Active</label>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title="Delete user?" message={`Permanently remove "${toDelete?.full_name}"?`}
        confirmLabel="Delete" loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
