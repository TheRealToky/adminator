import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Tag, PackagePlus, ChefHat, X } from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';

import { catalog, inventory } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { processedMaterials as processedMaterialsApi } from '@/api/processed-materials';
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
import { formatMoney, formatQuantity } from '@/lib/format';
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
  const [usageFor, setUsageFor] = useState<RawMaterial | null>(null);

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
    { key: 'thresh', header: t('rawMaterials.columns.reorder'), align: 'right', render: (r) => formatQuantity(r.reorder_threshold) },
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
        <button
          className="btn-ghost p-1.5 text-blue-700"
          title={t('rawMaterials.actions.usedIn')}
          onClick={(e) => { e.stopPropagation(); setUsageFor(r); }}
        >
          <ChefHat size={14} />
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
            <input type="number" step="0.0001" className="input" value={form.reorder_threshold ?? '0'} onChange={(e) => setForm({ ...form, reorder_threshold: e.target.value })} />
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
            type="number" step="0.0001"
            className="input"
            value={receiveQty}
            onChange={(e) => setReceiveQty(e.target.value)}
          />
          <p className="text-xs text-slate-500 mt-2">
            {t('rawMaterials.receive.hint')}
          </p>
        </div>
      </Modal>

      <UsageModal material={usageFor} onClose={() => setUsageFor(null)} />

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

// ── Usage modal (products & processed materials using this raw material) ──
function UsageModal({
  material: materialProp,
  onClose,
}: {
  material: RawMaterial | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { t } = useTranslation();

  // Read live material data so the list updates as we remove items, without
  // depending on the parent list query to refresh.
  const materialQuery = useQuery({
    queryKey: ['raw-material', materialProp?.id],
    queryFn: () => catalog.rawMaterials.get(materialProp!.id),
    enabled: !!materialProp,
  });
  const material = materialQuery.data ?? materialProp;

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['raw-material', material?.id] });
    qc.invalidateQueries({ queryKey: ['raw-materials'] });
    qc.invalidateQueries({ queryKey: ['materials-all'] });
    qc.invalidateQueries({ queryKey: ['products'] });
    qc.invalidateQueries({ queryKey: ['processed-materials'] });
    qc.invalidateQueries({ queryKey: ['processed-materials-all'] });
  };

  const removeRecipeItem = useMutation({
    mutationFn: (id: string) => catalog.recipes.remove(id),
    onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const removeProcessedRecipeItem = useMutation({
    mutationFn: (id: string) => processedMaterialsApi.recipes.remove(id),
    onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const products = material?.used_in_products ?? [];
  const processed = material?.used_in_processed_materials ?? [];
  const hasAny = products.length > 0 || processed.length > 0;

  return (
    <Modal
      open={!!materialProp}
      onClose={onClose}
      title={t('rawMaterials.usage.title', { name: material?.name ?? '' })}
      size="lg"
    >
      <p className="text-sm text-slate-500 mb-4">
        <Trans i18nKey="rawMaterials.usage.lead" components={{ 1: <strong /> }} />
      </p>

      {!hasAny && (
        <p className="px-3 py-6 text-center text-sm text-slate-400 border border-slate-200 rounded-md">
          {t('rawMaterials.usage.empty')}
        </p>
      )}

      {products.length > 0 && (
        <section className="mb-4">
          <h4 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
            {t('rawMaterials.usage.productsHeader')}
          </h4>
          <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
            {products.map((it) => (
              <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
                <span className="col-span-7 text-sm flex items-center gap-2">
                  <span className="badge-gray">{t('rawMaterials.usage.badgeProduct')}</span>
                  <span className="font-medium">{it.product_name}</span>
                  <span className="text-xs text-slate-500 font-mono">{it.product_sku}</span>
                </span>
                <span className="col-span-4 text-right text-sm">
                  {formatQuantity(it.quantity)} {material?.unit}
                </span>
                <button
                  className="col-span-1 text-red-500 hover:text-red-700 justify-self-end"
                  title={t('common.removed')}
                  disabled={removeRecipeItem.isPending}
                  onClick={() => removeRecipeItem.mutate(it.id)}
                >
                  <X size={16} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {processed.length > 0 && (
        <section>
          <h4 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
            {t('rawMaterials.usage.processedHeader')}
          </h4>
          <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
            {processed.map((it) => (
              <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
                <span className="col-span-7 text-sm flex items-center gap-2">
                  <span className="badge-blue">{t('rawMaterials.usage.badgeProcessed')}</span>
                  <span className="font-medium">{it.processed_material_name}</span>
                  <span className="text-xs text-slate-500 font-mono">{it.processed_material_sku}</span>
                </span>
                <span className="col-span-4 text-right text-sm">
                  {formatQuantity(it.quantity)} {material?.unit}
                </span>
                <button
                  className="col-span-1 text-red-500 hover:text-red-700 justify-self-end"
                  title={t('common.removed')}
                  disabled={removeProcessedRecipeItem.isPending}
                  onClick={() => removeProcessedRecipeItem.mutate(it.id)}
                >
                  <X size={16} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-slate-500 mt-4">
        {t('rawMaterials.usage.hint')}
      </p>
    </Modal>
  );
}
