import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Tag, PackagePlus } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { catalog, inventory } from '@/api/endpoints';
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
import { formatMoney, formatNumber } from '@/lib/format';
import type { RawMaterial } from '@/api/types';

const empty: Partial<RawMaterial> = {
  sku: '', name: '', unit: 'g', unit_cost: '0', reorder_threshold: '0',
  preferred_supplier: null, is_active: true,
};

export function RawMaterialsPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<RawMaterial>({
    queryKey: ['raw-materials'],
    fetcher: (p) => catalog.rawMaterials.list(p),
    deleter: (id) => catalog.rawMaterials.remove(id),
  });

  const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
  const suppliers = useQuery({ queryKey: ['suppliers-all'], queryFn: () => catalog.suppliers.list({ page_size: 200 }) });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<RawMaterial | null>(null);
  const [form, setForm] = useState<Partial<RawMaterial>>(empty);
  const [toDelete, setToDelete] = useState<RawMaterial | null>(null);
  const [receiveOpen, setReceiveOpen] = useState<RawMaterial | null>(null);
  const [receiveQty, setReceiveQty] = useState('');

  const save = useMutation({
    mutationFn: () =>
      editing ? catalog.rawMaterials.update(editing.id, form) : catalog.rawMaterials.create(form),
    onSuccess: () => {
      toast.success(editing ? t('rawMaterials.updated') : t('rawMaterials.created'));
      qc.invalidateQueries({ queryKey: ['raw-materials'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const receive = useMutation({
    mutationFn: () =>
      inventory.stock.receive({
        raw_material: receiveOpen!.id,
        quantity: Number(receiveQty),
        reference: 'Purchase',
      }),
    onSuccess: () => {
      toast.success(t('rawMaterials.received', { qty: receiveQty, unit: receiveOpen?.unit ?? '' }));
      qc.invalidateQueries({ queryKey: ['stock'] });
      setReceiveOpen(null);
      setReceiveQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function openEdit(row: RawMaterial) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<RawMaterial>[] = [
    { key: 'sku', header: t('rawMaterials.columns.sku'), render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
    { key: 'name', header: t('rawMaterials.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'unit', header: t('rawMaterials.columns.unit'), render: (r) => r.unit },
    { key: 'cost', header: t('rawMaterials.columns.cost'), align: 'right', render: (r) => formatMoney(r.unit_cost) },
    { key: 'thresh', header: t('rawMaterials.columns.reorder'), align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
    { key: 'supplier', header: t('rawMaterials.columns.supplier'), render: (r) => r.preferred_supplier_name ?? '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5 text-emerald-700"
          title={t('rawMaterials.receive.receiveStock')}
          onClick={(e) => { e.stopPropagation(); setReceiveOpen(r); }}
        >
          <PackagePlus size={14} />
        </button>
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}>
          <Pencil size={14} />
        </button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}>
          <Trash2 size={14} />
        </button>
      </div>
    )},
  ];

  const exportColumns: ExportColumn<RawMaterial>[] = [
    { key: 'sku', header: t('rawMaterials.exportCols.sku'), value: (r) => r.sku },
    { key: 'name', header: t('rawMaterials.exportCols.name'), value: (r) => r.name },
    { key: 'unit', header: t('rawMaterials.exportCols.unit'), value: (r) => r.unit },
    { key: 'unit_cost', header: t('rawMaterials.exportCols.unitCost'), value: (r) => Number(r.unit_cost) },
    { key: 'reorder_threshold', header: t('rawMaterials.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
    { key: 'preferred_supplier', header: t('rawMaterials.exportCols.preferredSupplier'), value: (r) => r.preferred_supplier_name ?? '' },
    { key: 'is_active', header: t('rawMaterials.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
  ];

  return (
    <>
      <PageHeader
        title={t('rawMaterials.title')}
        subtitle={t('rawMaterials.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="raw-materials"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => catalog.rawMaterials.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('rawMaterials.new')}</button>
          </>
        }
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('rawMaterials.searchPlaceholder')} />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Tag} title={t('rawMaterials.emptyTitle')} description={t('rawMaterials.emptyDescription')} />}
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
        title={editing ? t('rawMaterials.edit') : t('rawMaterials.newTitle')}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending || !form.name || !form.sku}>
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">{t('rawMaterials.fields.sku')}</label>
            <input className="input font-mono" value={form.sku ?? ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('rawMaterials.fields.name')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('rawMaterials.fields.unit')}</label>
            <select className="input" value={form.unit ?? 'g'} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              {units.data?.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t('rawMaterials.fields.costPerUnit')}</label>
            <input type="number" step="0.0001" className="input" value={form.unit_cost ?? '0'} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('rawMaterials.fields.reorderThreshold')}</label>
            <input type="number" step="0.01" className="input" value={form.reorder_threshold ?? '0'} onChange={(e) => setForm({ ...form, reorder_threshold: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('rawMaterials.fields.preferredSupplier')}</label>
            <select
              className="input"
              value={form.preferred_supplier ?? ''}
              onChange={(e) => setForm({ ...form, preferred_supplier: e.target.value || null })}
            >
              <option value="">{t('common.none')}</option>
              {suppliers.data?.results.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-rm" type="checkbox" checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-rm" className="text-sm">{t('rawMaterials.fields.active')}</label>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!receiveOpen}
        onClose={() => setReceiveOpen(null)}
        title={t('rawMaterials.receive.title', { name: receiveOpen?.name ?? '' })}
        size="sm"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setReceiveOpen(null)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={!receiveQty || Number(receiveQty) <= 0 || receive.isPending}
              onClick={() => receive.mutate()}
            >
              {receive.isPending ? t('rawMaterials.receive.recording') : t('rawMaterials.receive.record')}
            </button>
          </>
        }
      >
        <div>
          <label className="label">{t('rawMaterials.receive.qtyLabel', { unit: receiveOpen?.unit ?? '' })}</label>
          <input
            autoFocus
            type="number" step="0.01"
            className="input"
            value={receiveQty}
            onChange={(e) => setReceiveQty(e.target.value)}
          />
          <p className="text-xs text-slate-500 mt-2">
            {t('rawMaterials.receive.hint')}
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('rawMaterials.deleteTitle')}
        message={t('rawMaterials.deleteMessage', { name: toDelete?.name ?? '' })}
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
