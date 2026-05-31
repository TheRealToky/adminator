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
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
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
  const { t } = useTranslation();
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
      toast.success(editing ? t('users.updated') : t('users.created'));
      qc.invalidateQueries({ queryKey: ['users'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const toggle = useMutation({
    mutationFn: (u: User) => u.is_active ? usersApi.deactivate(u.id) : usersApi.activate(u.id),
    onSuccess: () => { toast.success(t('common.updated')); qc.invalidateQueries({ queryKey: ['users'] }); },
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
    { key: 'name', header: t('users.columns.name'), render: (r) => (
      <div>
        <p className="font-medium">{r.full_name}</p>
        <p className="text-xs text-slate-500">{r.email}</p>
      </div>
    )},
    { key: 'phone', header: t('users.columns.phone'), render: (r) => r.phone || '—' },
    { key: 'role', header: t('users.columns.role'), render: (r) => <span className={ROLE_BADGE[r.role] ?? 'badge-gray'}>{r.role}</span> },
    { key: 'status', header: t('users.columns.status'), render: (r) =>
      r.is_active
        ? <span className="badge-green">{t('common.active')}</span>
        : <span className="badge-gray">{t('common.inactive')}</span>
    },
    { key: 'joined', header: t('users.columns.joined'), render: (r) => formatDate(r.date_joined) },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5"
          title={r.is_active ? t('users.actions.deactivate') : t('users.actions.activate')}
          onClick={(e) => { e.stopPropagation(); toggle.mutate(r); }}
        >
          {r.is_active ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
        </button>
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}><Pencil size={14} /></button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}><Trash2 size={14} /></button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<User>[] = [
    { key: 'full_name', header: t('users.exportCols.name'), value: (r) => r.full_name },
    { key: 'email', header: t('users.exportCols.email'), value: (r) => r.email },
    { key: 'phone', header: t('users.exportCols.phone'), value: (r) => r.phone },
    { key: 'role', header: t('users.exportCols.role'), value: (r) => r.role },
    { key: 'is_active', header: t('users.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    { key: 'date_joined', header: t('users.exportCols.joined'), value: (r) => r.date_joined },
  ];

  return (
    <>
      <PageHeader
        title={t('users.title')}
        subtitle={t('users.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="staff"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => usersApi.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('users.new')}</button>
          </>
        }
      />
      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('users.searchPlaceholder')} />
        </div>
        <DataTable columns={columns} data={list.data?.results} loading={list.isLoading} rowKey={(r) => r.id}
          empty={<EmptyState icon={Users2} title={t('users.emptyTitle')} />} />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open} onClose={() => setOpen(false)}
        title={editing ? t('users.editModal', { name: editing.full_name }) : t('users.newModal')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={!form.email || !form.full_name || (!editing && !form.password) || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">{t('users.fields.fullName')}</label>
            <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('users.fields.email')}</label>
            <input type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('users.fields.phone')}</label>
            <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('users.fields.role')}</label>
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
              <label className="label">{t('users.fields.password')}</label>
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
            <label htmlFor="active-user" className="text-sm">{t('users.fields.active')}</label>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete} onClose={() => setToDelete(null)}
        title={t('users.deleteTitle')} message={t('users.deleteMessage', { name: toDelete?.full_name ?? '' })}
        confirmLabel={t('common.delete')} loading={list.deleteMutation.isPending}
        onConfirm={() => { if (toDelete) list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) }); }}
      />
    </>
  );
}
