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
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import type { Supplier } from '@/api/types';

const empty: Partial<Supplier> = {
  name: '', contact_name: '', phone: '', email: '', address: '', notes: '', is_active: true,
};

export function SuppliersPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Supplier>({
    queryKey: ['suppliers'],
    fetcher: (p) => catalog.suppliers.list(p),
    deleter: (id) => catalog.suppliers.remove(id),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [form, setForm] = useState<Partial<Supplier>>(empty);
  const [toDelete, setToDelete] = useState<Supplier | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? catalog.suppliers.update(editing.id, form) : catalog.suppliers.create(form),
    onSuccess: () => {
      toast.success(editing ? t('suppliers.updated') : t('suppliers.created'));
      qc.invalidateQueries({ queryKey: ['suppliers'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function openEdit(row: Supplier) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<Supplier>[] = [
    { key: 'name', header: t('suppliers.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'contact', header: t('suppliers.columns.contact'), render: (r) => r.contact_name || '—' },
    { key: 'phone', header: t('suppliers.columns.phone'), render: (r) => r.phone || '—' },
    { key: 'email', header: t('suppliers.columns.email'), render: (r) => r.email || '—' },
    { key: 'active', header: t('suppliers.columns.status'), render: (r) => (
      r.is_active
        ? <span className="badge-green">{t('common.active')}</span>
        : <span className="badge-gray">{t('common.inactive')}</span>
    )},
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}>
          <Pencil size={14} />
        </button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}>
          <Trash2 size={14} />
        </button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<Supplier>[] = [
    { key: 'name', header: t('suppliers.exportCols.name'), value: (r) => r.name },
    { key: 'contact_name', header: t('suppliers.exportCols.contact'), value: (r) => r.contact_name },
    { key: 'phone', header: t('suppliers.exportCols.phone'), value: (r) => r.phone },
    { key: 'email', header: t('suppliers.exportCols.email'), value: (r) => r.email },
    { key: 'address', header: t('suppliers.exportCols.address'), value: (r) => r.address },
    { key: 'notes', header: t('suppliers.exportCols.notes'), value: (r) => r.notes },
    { key: 'is_active', header: t('suppliers.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
  ];

  return (
    <>
      <PageHeader
        title={t('suppliers.title')}
        subtitle={t('suppliers.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="suppliers"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => catalog.suppliers.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('suppliers.new')}</button>
          </>
        }
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('suppliers.searchPlaceholder')} />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Building2} title={t('suppliers.emptyTitle')} description={t('suppliers.emptyDescription')} />}
        />
        {list.data && (
          <Pagination
            page={list.page}
            pageSize={list.pageSize}
            total={list.data.count}
            onChange={list.setPage}
          />
        )}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('suppliers.edit') : t('suppliers.new')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending || !form.name}>
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">{t('suppliers.fields.companyName')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('suppliers.fields.contact')}</label>
            <input className="input" value={form.contact_name ?? ''} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('suppliers.fields.phone')}</label>
            <input className="input" value={form.phone ?? ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('suppliers.fields.email')}</label>
            <input type="email" className="input" value={form.email ?? ''} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('suppliers.fields.address')}</label>
            <textarea className="input" rows={2} value={form.address ?? ''} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('suppliers.fields.notes')}</label>
            <textarea className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input
              id="active" type="checkbox"
              checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <label htmlFor="active" className="text-sm">{t('suppliers.fields.active')}</label>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('suppliers.deleteTitle')}
        message={t('suppliers.deleteMessage', { name: toDelete?.name ?? '' })}
        confirmLabel={t('common.delete')}
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (!toDelete) return;
          list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
        }}
      />
    </>
  );
}
