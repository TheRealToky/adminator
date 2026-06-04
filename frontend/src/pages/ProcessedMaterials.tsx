import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Pencil, Trash2, Layers, X, ChefHat, PlayCircle, History, Sliders,
} from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';

import { catalog } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { processedMaterials } from '@/api/processed-materials';
import type {
  ProcessedMaterial,
  ProcessedMaterialBatch,
  ProcessedMaterialStockMovement,
} from '@/api/processed-materials';

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
import { formatDate, formatDateTime, formatMoney, formatNumber, formatQuantity } from '@/lib/format';

type Tab = 'materials' | 'batches' | 'movements';

export function ProcessedMaterialsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('materials');

  const tabs: { key: Tab; label: string; icon: typeof ChefHat }[] = [
    { key: 'materials', label: t('processedMaterials.tabs.materials'), icon: ChefHat },
    { key: 'batches', label: t('processedMaterials.tabs.batches'), icon: PlayCircle },
    { key: 'movements', label: t('processedMaterials.tabs.movements'), icon: History },
  ];

  return (
    <>
      <PageHeader
        title={t('processedMaterials.title')}
        subtitle={t('processedMaterials.subtitle')}
      />

      <div className="card">
        <div className="card-header gap-2 flex-wrap">
          <div className="flex gap-1">
            {tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${
                  tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'materials' && <MaterialsTab />}
        {tab === 'batches' && <BatchesTab />}
        {tab === 'movements' && <MovementsTab />}
      </div>
    </>
  );
}

// ── Materials tab ─────────────────────────────────────────────────────────
const emptyMaterial: Partial<ProcessedMaterial> = {
  sku: '', name: '', unit: 'g', yield_per_batch: '1000',
  shelf_life_hours: 24, reorder_threshold: '0', notes: '', is_active: true,
};

function MaterialsTab() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<ProcessedMaterial>({
    queryKey: ['processed-materials'],
    fetcher: (p) => processedMaterials.list(p),
    deleter: (id) => processedMaterials.remove(id),
  });
  const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ProcessedMaterial | null>(null);
  const [form, setForm] = useState<Partial<ProcessedMaterial>>(emptyMaterial);
  const [toDelete, setToDelete] = useState<ProcessedMaterial | null>(null);

  // Recipe + usage modals
  const [recipeFor, setRecipeFor] = useState<ProcessedMaterial | null>(null);
  const [usageFor, setUsageFor] = useState<ProcessedMaterial | null>(null);

  // Adjust + produce + write-off
  const [adjustFor, setAdjustFor] = useState<ProcessedMaterial | null>(null);
  const [produceFor, setProduceFor] = useState<ProcessedMaterial | null>(null);
  const [writeOffFor, setWriteOffFor] = useState<ProcessedMaterial | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? processedMaterials.update(editing.id, form) : processedMaterials.create(form),
    onSuccess: () => {
      toast.success(editing ? t('processedMaterials.list.updated') : t('processedMaterials.list.created'));
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(emptyMaterial); setOpen(true); }
  function openEdit(row: ProcessedMaterial) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<ProcessedMaterial>[] = [
    { key: 'sku', header: t('processedMaterials.columns.sku'), render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
    { key: 'name', header: t('processedMaterials.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'unit', header: t('processedMaterials.columns.unit'), render: (r) => r.unit },
    { key: 'yield', header: t('processedMaterials.columns.yieldBatch'), align: 'right', render: (r) => (
      `${formatQuantity(r.yield_per_batch)} ${r.unit}`
    )},
    { key: 'cost', header: t('processedMaterials.columns.costUnit'), align: 'right', render: (r) => formatMoney(r.unit_cost) },
    { key: 'stock', header: t('processedMaterials.columns.onHand'), align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatQuantity(r.stock_quantity)} {r.unit}
      </span>
    )},
    { key: 'status', header: '', render: (r) => (
      r.is_low
        ? <span className="badge-red">{t('inventory.badges.low')}</span>
        : <span className="badge-green">{t('inventory.badges.ok')}</span>
    )},
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5 text-emerald-700"
          title={t('processedMaterials.actions.produceBatch')}
          onClick={(e) => { e.stopPropagation(); setProduceFor(r); }}
        >
          <PlayCircle size={14} />
        </button>
        <button
          className="btn-ghost p-1.5 text-brand-700"
          title={t('processedMaterials.actions.recipe')}
          onClick={(e) => { e.stopPropagation(); setRecipeFor(r); }}
        >
          <Layers size={14} />
        </button>
        <button
          className="btn-ghost p-1.5 text-blue-700"
          title={t('processedMaterials.actions.usedInProducts')}
          onClick={(e) => { e.stopPropagation(); setUsageFor(r); }}
        >
          <ChefHat size={14} />
        </button>
        <button
          className="btn-ghost p-1.5"
          title={t('processedMaterials.actions.adjustStock')}
          onClick={(e) => { e.stopPropagation(); setAdjustFor(r); }}
        >
          <Sliders size={14} />
        </button>
        <button
          className="btn-ghost p-1.5 text-red-500"
          title={t('processedMaterials.actions.writeOffStock')}
          disabled={Number(r.stock_quantity) <= 0}
          onClick={(e) => { e.stopPropagation(); setWriteOffFor(r); }}
        >
          <Trash2 size={14} />
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

  const exportColumns: ExportColumn<ProcessedMaterial>[] = [
    { key: 'sku', header: t('processedMaterials.exportCols.sku'), value: (r) => r.sku },
    { key: 'name', header: t('processedMaterials.exportCols.name'), value: (r) => r.name },
    { key: 'unit', header: t('processedMaterials.exportCols.unit'), value: (r) => r.unit },
    { key: 'yield_per_batch', header: t('processedMaterials.exportCols.yieldPerBatch'), value: (r) => Number(r.yield_per_batch) },
    { key: 'unit_cost', header: t('processedMaterials.exportCols.unitCost'), value: (r) => Number(r.unit_cost) },
    { key: 'overhead_pct', header: t('processedMaterials.exportCols.overheadPct'), value: (r) => Number(r.overhead_pct) },
    { key: 'shelf_life_hours', header: t('processedMaterials.exportCols.shelfLifeHours'), value: (r) => r.shelf_life_hours },
    { key: 'reorder_threshold', header: t('processedMaterials.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
    { key: 'stock_quantity', header: t('processedMaterials.exportCols.onHand'), value: (r) => Number(r.stock_quantity) },
    { key: 'is_low', header: t('processedMaterials.exportCols.lowStock'), value: (r) => (r.is_low ? t('common.yes') : t('common.no')) },
    { key: 'is_active', header: t('processedMaterials.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    { key: 'notes', header: t('processedMaterials.exportCols.notes'), value: (r) => r.notes },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('processedMaterials.list.searchPlaceholder')} />
        <div className="flex items-center gap-2">
          <ExportMenu
            filename="processed-materials"
            columns={exportColumns}
            fetchRows={() => fetchAllPaginated(
              (p) => processedMaterials.list(p),
              list.search ? { search: list.search } : {},
            )}
          />
          <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('processedMaterials.list.new')}</button>
        </div>
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState
          icon={ChefHat}
          title={t('processedMaterials.list.emptyTitle')}
          description={t('processedMaterials.list.emptyDescription')}
        />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      {/* CRUD modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t('processedMaterials.list.editModal', { name: editing.name }) : t('processedMaterials.list.newModal')}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={!form.name || !form.sku || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">{t('processedMaterials.fields.sku')}</label>
            <input className="input font-mono" value={form.sku ?? ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('processedMaterials.fields.name')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('processedMaterials.fields.unit')}</label>
            <select className="input" value={form.unit ?? 'g'} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              {units.data?.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t('processedMaterials.fields.yieldPerBatch')}</label>
            <input type="number" step="0.0001" className="input" value={form.yield_per_batch ?? '1'}
              onChange={(e) => setForm({ ...form, yield_per_batch: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('processedMaterials.fields.shelfLifeHours')}</label>
            <input type="number" className="input" value={form.shelf_life_hours ?? 24}
              onChange={(e) => setForm({ ...form, shelf_life_hours: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label">{t('processedMaterials.fields.reorderThreshold')}</label>
            <input type="number" step="0.0001" className="input" value={form.reorder_threshold ?? '0'}
              onChange={(e) => setForm({ ...form, reorder_threshold: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('processedMaterials.fields.notes')}</label>
            <textarea className="input" rows={2} value={form.notes ?? ''}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-pm" type="checkbox" checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-pm" className="text-sm">{t('processedMaterials.fields.active')}</label>
          </div>
        </div>
      </Modal>

      <RecipeModal open={!!recipeFor} material={recipeFor} onClose={() => setRecipeFor(null)} />
      <UsageModal open={!!usageFor} material={usageFor} onClose={() => setUsageFor(null)} />
      <AdjustModal material={adjustFor} onClose={() => setAdjustFor(null)} />
      <WriteOffModal material={writeOffFor} onClose={() => setWriteOffFor(null)} />
      <ProduceModal material={produceFor} onClose={() => setProduceFor(null)} />

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('processedMaterials.list.deleteTitle')}
        message={t('processedMaterials.list.deleteMessage', { name: toDelete?.name ?? '' })}
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

// ── Recipe modal (ingredients used to make ONE batch) ─────────────────────
type IngredientKind = 'raw' | 'processed';

function RecipeModal({
  open, material: materialProp, onClose,
}: { open: boolean; material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const rawMaterials = useQuery({
    queryKey: ['materials-all'],
    queryFn: () => catalog.rawMaterials.list({ page_size: 500 }),
  });
  const processedMaterialsList = useQuery({
    queryKey: ['processed-materials-all'],
    queryFn: () => processedMaterials.list({ page_size: 500 }),
  });
  // Always read live material data (overhead_pct, yield, unit_cost) so the
  // form reflects edits without needing a parent reopen.
  const materialQuery = useQuery({
    queryKey: ['processed-material', materialProp?.id],
    queryFn: () => processedMaterials.get(materialProp!.id),
    enabled: !!materialProp,
  });
  const material = materialQuery.data ?? materialProp;
  // Fetch the recipe lines on their own query so the list updates live as we
  // add/remove items — the parent list query lags behind the modal.
  const recipeQuery = useQuery({
    queryKey: ['processed-recipes', material?.id],
    queryFn: () => processedMaterials.recipes.list({
      processed_material: material!.id, page_size: 200,
    }),
    enabled: !!material,
  });
  const items = recipeQuery.data?.results ?? [];

  const [kind, setKind] = useState<IngredientKind>('raw');
  const [newIngredient, setNewIngredient] = useState('');
  const [newQty, setNewQty] = useState('');
  const [overheadPct, setOverheadPct] = useState<string>(material?.overhead_pct ?? '0');
  useEffect(() => { setOverheadPct(material?.overhead_pct ?? '0'); }, [material?.id, material?.overhead_pct]);
  // Reset dropdown when switching kind — the option ids don't overlap, but the
  // placeholder feels clearer this way.
  useEffect(() => { setNewIngredient(''); }, [kind]);

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['processed-recipes', material?.id] });
    qc.invalidateQueries({ queryKey: ['processed-material', material?.id] });
    qc.invalidateQueries({ queryKey: ['processed-materials'] });
    qc.invalidateQueries({ queryKey: ['processed-materials-all'] });
  };

  const add = useMutation({
    mutationFn: () => processedMaterials.recipes.create({
      processed_material: material!.id,
      raw_material: kind === 'raw' ? newIngredient : null,
      sub_processed_material: kind === 'processed' ? newIngredient : null,
      quantity: newQty,
    }),
    onSuccess: () => {
      toast.success(t('processedMaterials.recipe.added'));
      invalidateAll();
      setNewIngredient(''); setNewQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => processedMaterials.recipes.remove(id),
    onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
  });
  const saveOverhead = useMutation({
    mutationFn: (pct: string) => processedMaterials.update(material!.id, { overhead_pct: pct }),
    onSuccess: () => { toast.success(t('processedMaterials.recipe.overheadSaved')); invalidateAll(); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const rows = items.map((it) => {
    const isSub = !!it.sub_processed_material;
    const unitCost = Number(
      isSub ? it.sub_processed_material_unit_cost : it.raw_material_unit_cost,
    ) || 0;
    return {
      ...it,
      isSub,
      ingredientName: isSub ? it.sub_processed_material_name : it.raw_material_name,
      ingredientUnit: isSub ? it.sub_processed_material_unit : it.raw_material_unit,
      lineCost: Number(it.quantity) * unitCost,
    };
  });
  const ingredientCost = rows.reduce((sum, r) => sum + r.lineCost, 0);
  const overheadNum = Number(overheadPct) || 0;
  const overheadAmount = ingredientCost * overheadNum / 100;
  const totalBatchCost = ingredientCost + overheadAmount;
  const yieldPerBatch = Number(material?.yield_per_batch) || 0;
  const perUnitCost = yieldPerBatch > 0 ? totalBatchCost / yieldPerBatch : 0;
  const overheadDirty = material != null
    && Number(overheadPct || 0) !== Number(material.overhead_pct ?? 0);

  return (
    <Modal open={open} onClose={onClose}
      title={t('processedMaterials.recipe.title', { name: material?.name ?? '' })}
      size="lg"
    >
      <p className="text-sm text-slate-500 mb-4">
        <Trans
          i18nKey="processedMaterials.recipe.lead"
          values={{
            yield: formatQuantity(material?.yield_per_batch ?? 0),
            unit: material?.unit ?? '',
          }}
          components={{ 1: <strong /> }}
        />
      </p>
      <div className="grid grid-cols-12 gap-2 mb-2 px-3 text-xs uppercase tracking-wider text-slate-500">
        <span className="col-span-6">{t('processedMaterials.recipe.ingredient')}</span>
        <span className="col-span-3 text-right">{t('processedMaterials.recipe.quantity')}</span>
        <span className="col-span-2 text-right">{t('processedMaterials.recipe.cost')}</span>
        <span className="col-span-1" />
      </div>
      <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">{t('processedMaterials.recipe.empty')}</li>
        )}
        {rows.map((it) => (
          <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
            <span className="col-span-6 text-sm flex items-center gap-2">
              {it.ingredientName}
              {it.isSub && (
                <span className="badge-gray text-[10px]" title={t('processedMaterials.recipe.processedTip')}>
                  {t('processedMaterials.recipe.processedBadge')}
                </span>
              )}
            </span>
            <span className="col-span-3 text-right text-sm">
              {formatQuantity(it.quantity)} {it.ingredientUnit}
            </span>
            <span className="col-span-2 text-right text-sm text-slate-600">
              {formatMoney(it.lineCost)}
            </span>
            <button
              className="col-span-1 text-red-500 hover:text-red-700 justify-self-end"
              onClick={() => remove.mutate(it.id)}
            >
              <X size={16} />
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex gap-1 text-xs">
        {([
          { key: 'raw' as const, label: t('processedMaterials.recipe.kindRaw') },
          { key: 'processed' as const, label: t('processedMaterials.recipe.kindProcessed') },
        ]).map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setKind(key)}
            className={`px-2.5 py-1 rounded-md font-medium ${
              kind === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-12 gap-2 mt-2 items-end">
        <div className="col-span-7">
          <label className="label">
            {kind === 'raw' ? t('processedMaterials.recipe.addRaw') : t('processedMaterials.recipe.addProcessed')}
          </label>
          <select
            className="input"
            value={newIngredient}
            onChange={(e) => setNewIngredient(e.target.value)}
          >
            <option value="">{t('common.select')}</option>
            {kind === 'raw'
              ? rawMaterials.data?.results.map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.unit})</option>
                ))
              : processedMaterialsList.data?.results
                  .filter((m) => m.id !== material?.id)
                  .map((m) => (
                    <option key={m.id} value={m.id}>{m.name} ({m.unit})</option>
                  ))}
          </select>
        </div>
        <div className="col-span-4">
          <label className="label">{t('processedMaterials.recipe.qtyPerBatch')}</label>
          <input type="number" step="0.0001" className="input"
            value={newQty} onChange={(e) => setNewQty(e.target.value)} />
        </div>
        <button
          className="col-span-1 btn-primary px-2 py-2"
          disabled={!newIngredient || !newQty || add.isPending}
          onClick={() => add.mutate()}
          aria-label={t('common.add')}
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="mt-6 border-t border-slate-200 pt-4 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600">{t('processedMaterials.recipe.ingredientSubtotal')}</span>
          <span className="font-medium tabular-nums">{formatMoney(ingredientCost)}</span>
        </div>
        <div className="grid grid-cols-12 gap-2 items-center">
          <label className="col-span-6 text-sm text-slate-600" htmlFor="pm-overhead-pct">
            {t('processedMaterials.recipe.overheadLabel')}
          </label>
          <div className="col-span-3">
            <input
              id="pm-overhead-pct"
              type="number"
              step="0.01"
              min="0"
              className="input text-right"
              value={overheadPct}
              onChange={(e) => setOverheadPct(e.target.value)}
              disabled={!material}
            />
          </div>
          <span className="col-span-3 text-right text-sm font-medium tabular-nums text-slate-700">
            {formatMoney(overheadAmount)}
          </span>
        </div>
        {overheadDirty && (
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="btn-secondary text-xs px-2 py-1"
              onClick={() => setOverheadPct(material?.overhead_pct ?? '0')}
              disabled={saveOverhead.isPending}
            >
              {t('common.reset')}
            </button>
            <button
              type="button"
              className="btn-primary text-xs px-2 py-1"
              onClick={() => saveOverhead.mutate(overheadPct)}
              disabled={saveOverhead.isPending}
            >
              {saveOverhead.isPending ? t('common.saving') : t('processedMaterials.recipe.saveOverhead')}
            </button>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 pt-2 text-sm">
          <span className="font-medium text-slate-800">{t('processedMaterials.recipe.totalBatchCost')}</span>
          <span className="font-semibold text-slate-900 tabular-nums">{formatMoney(totalBatchCost)}</span>
        </div>
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            {t('processedMaterials.recipe.perUnit', {
              yield: formatQuantity(material?.yield_per_batch ?? 0),
              unit: material?.unit ?? '',
            })}
          </span>
          <span className="tabular-nums">
            {t('processedMaterials.recipe.perUnitValue', {
              cost: formatMoney(perUnitCost),
              unit: material?.unit ?? 'unit',
            })}
          </span>
        </div>
      </div>
    </Modal>
  );
}

// ── Usage modal (products that use this processed material) ──────────────
function UsageModal({
  open, material, onClose,
}: { open: boolean; material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const products = useQuery({
    queryKey: ['products-all'],
    queryFn: () => catalog.products.list({ page_size: 500 }),
  });
  const items = material?.used_in_products ?? [];

  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('');

  const add = useMutation({
    mutationFn: () => processedMaterials.usages.create({
      product: productId,
      processed_material: material!.id,
      quantity: qty,
    }),
    onSuccess: () => {
      toast.success(t('processedMaterials.usage.added'));
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      setProductId(''); setQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => processedMaterials.usages.remove(id),
    onSuccess: () => {
      toast.success(t('common.removed'));
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
    },
  });

  return (
    <Modal open={open} onClose={onClose}
      title={t('processedMaterials.usage.title', { name: material?.name ?? '' })}
      size="lg"
    >
      <p className="text-sm text-slate-500 mb-4">
        <Trans i18nKey="processedMaterials.usage.lead" components={{ 1: <strong /> }} />
      </p>
      <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {items.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">{t('processedMaterials.usage.empty')}</li>
        )}
        {items.map((it) => (
          <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
            <span className="col-span-7 text-sm">{it.product_name}</span>
            <span className="col-span-4 text-right text-sm">
              {formatQuantity(it.quantity)} {material?.unit}
            </span>
            <button
              className="col-span-1 text-red-500 hover:text-red-700 justify-self-end"
              onClick={() => remove.mutate(it.id)}
            >
              <X size={16} />
            </button>
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-12 gap-2 mt-4 items-end">
        <div className="col-span-7">
          <label className="label">{t('processedMaterials.usage.addProduct')}</label>
          <select className="input" value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">{t('common.select')}</option>
            {products.data?.results.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div className="col-span-4">
          <label className="label">{t('processedMaterials.usage.qtyPerUnit')}</label>
          <input type="number" step="0.0001" className="input"
            value={qty} onChange={(e) => setQty(e.target.value)} />
        </div>
        <button
          className="col-span-1 btn-primary px-2 py-2"
          disabled={!productId || !qty || add.isPending}
          onClick={() => add.mutate()}
          aria-label={t('common.add')}
        >
          <Plus size={16} />
        </button>
      </div>
    </Modal>
  );
}

// ── Adjust stock ──────────────────────────────────────────────────────────
function AdjustModal({ material, onClose }: { material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [delta, setDelta] = useState('');
  const [note, setNote] = useState('');

  const mutate = useMutation({
    mutationFn: () => processedMaterials.stock.adjust({
      processed_material: material!.id,
      quantity_delta: Number(delta),
      note,
    }),
    onSuccess: () => {
      toast.success(t('processedMaterials.adjust.recorded'));
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      qc.invalidateQueries({ queryKey: ['processed-movements'] });
      onClose(); setDelta(''); setNote('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!material) return null;
  return (
    <Modal
      open={!!material} onClose={onClose}
      title={t('processedMaterials.adjust.title', { name: material.name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!delta || Number(delta) === 0 || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending ? t('common.saving') : t('common.apply')}
          </button>
        </>
      }
    >
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('processedMaterials.adjust.currentOnHand', {
            qty: formatQuantity(material.stock_quantity),
            unit: material.unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">{t('processedMaterials.adjust.delta', { unit: material.unit })}</label>
          <input autoFocus type="number" step="0.0001" className="input"
            value={delta} onChange={(e) => setDelta(e.target.value)} />
        </div>
        <div>
          <label className="label">{t('common.noteOptional')}</label>
          <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Write off processed-material stock ────────────────────────────────────
function WriteOffModal({ material, onClose }: { material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [quantity, setQuantity] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');

  const mutate = useMutation({
    mutationFn: () => processedMaterials.stock.writeOff({
      processed_material: material!.id,
      quantity: Number(quantity),
      note,
      reference,
    }),
    onSuccess: () => {
      const qty = Number(quantity);
      const expense = qty * Number(material?.unit_cost ?? 0);
      toast.success(
        expense > 0
          ? t('processedMaterials.writeOff.recorded', {
              qty: formatQuantity(qty),
              unit: material?.unit ?? '',
              name: material?.name ?? '',
            })
          : t('processedMaterials.writeOff.recordedNoCost', {
              qty: formatQuantity(qty),
              unit: material?.unit ?? '',
              name: material?.name ?? '',
            }),
      );
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      qc.invalidateQueries({ queryKey: ['processed-stock'] });
      qc.invalidateQueries({ queryKey: ['processed-movements'] });
      qc.invalidateQueries({ queryKey: ['expenses'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
      setQuantity(''); setNote(''); setReference('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!material) return null;
  const onHand = Number(material.stock_quantity);
  const unitCost = Number(material.unit_cost || 0);
  const qty = Number(quantity) || 0;
  const exceedsStock = qty > onHand;
  const expense = qty * unitCost;

  return (
    <Modal
      open={!!material}
      onClose={onClose}
      title={t('processedMaterials.writeOff.title', { name: material.name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!quantity || qty <= 0 || exceedsStock || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending
              ? t('processedMaterials.writeOff.submitting')
              : t('processedMaterials.writeOff.submit')}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        {unitCost > 0 ? (
          <Trans
            i18nKey="processedMaterials.writeOff.lead"
            values={{ cost: formatMoney(unitCost), unit: material.unit }}
            components={{ 1: <strong /> }}
          />
        ) : (
          t('processedMaterials.writeOff.leadZeroCost')
        )}
      </p>
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('processedMaterials.writeOff.currentOnHand', {
            qty: formatQuantity(onHand),
            unit: material.unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">
            {t('processedMaterials.writeOff.quantity', { unit: material.unit })}
          </label>
          <input
            autoFocus type="number" step="0.0001" min="0" max={onHand}
            className="input"
            value={quantity} onChange={(e) => setQuantity(e.target.value)}
          />
          {exceedsStock && (
            <p className="text-xs text-red-600 mt-1">
              {t('processedMaterials.writeOff.exceedsOnHand', {
                qty: formatQuantity(onHand),
                unit: material.unit,
              })}
            </p>
          )}
        </div>
        <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 flex items-center justify-between">
          <span className="text-xs text-slate-600">{t('processedMaterials.writeOff.expenseToBook')}</span>
          <span className="text-sm font-semibold tabular-nums">
            {formatMoney(expense)}
          </span>
        </div>
        <div>
          <label className="label">{t('processedMaterials.writeOff.reason')}</label>
          <textarea
            className="input" rows={2}
            placeholder={t('processedMaterials.writeOff.reasonPlaceholder')}
            value={note} onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <div>
          <label className="label">{t('processedMaterials.writeOff.reference')}</label>
          <input
            className="input"
            value={reference} onChange={(e) => setReference(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  );
}

// ── Produce a batch ───────────────────────────────────────────────────────
function ProduceModal({ material, onClose }: { material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [batches, setBatches] = useState('1');
  const [scheduledFor, setScheduledFor] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');

  const produce = useMutation({
    mutationFn: () => processedMaterials.batches.produce({
      processed_material: material!.id,
      batches: Number(batches),
      scheduled_for: scheduledFor,
      notes,
    }),
    onSuccess: (batch) => {
      toast.success(t('processedMaterials.produce.produced', {
        qty: formatQuantity(batch.quantity_produced),
        unit: material?.unit ?? '',
      }));
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      qc.invalidateQueries({ queryKey: ['processed-batches'] });
      qc.invalidateQueries({ queryKey: ['processed-movements'] });
      qc.invalidateQueries({ queryKey: ['stock'] }); // raw materials decreased
      qc.invalidateQueries({ queryKey: ['movements'] });
      onClose(); setBatches('1'); setNotes('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!material) return null;
  const yieldPerBatch = Number(material.yield_per_batch);
  const projected = (Number(batches) || 0) * yieldPerBatch;

  return (
    <Modal
      open={!!material} onClose={onClose}
      title={t('processedMaterials.produce.title', { name: material.name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!batches || Number(batches) <= 0 || produce.isPending}
            onClick={() => produce.mutate()}
          >
            {produce.isPending ? t('processedMaterials.produce.producing') : t('processedMaterials.produce.produce')}
          </button>
        </>
      }
    >
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('processedMaterials.produce.lead', {
            yield: formatQuantity(material.yield_per_batch),
            unit: material.unit,
            projected: formatNumber(projected, 0),
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">{t('processedMaterials.produce.batches')}</label>
          <input autoFocus type="number" step="0.01" min="0.01" className="input"
            value={batches} onChange={(e) => setBatches(e.target.value)} />
        </div>
        <div>
          <label className="label">{t('processedMaterials.produce.scheduledFor')}</label>
          <input type="date" className="input"
            value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
        </div>
        <div>
          <label className="label">{t('processedMaterials.produce.notes')}</label>
          <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Batches tab ───────────────────────────────────────────────────────────
function BatchesTab() {
  const { t } = useTranslation();
  const list = useCrudList<ProcessedMaterialBatch>({
    queryKey: ['processed-batches'],
    fetcher: (p) => processedMaterials.batches.list(p),
    deleter: (id) => processedMaterials.batches.remove(id),
  });

  const columns: Column<ProcessedMaterialBatch>[] = [
    { key: 'sched', header: t('processedMaterials.batches.columns.scheduled'), render: (r) => formatDate(r.scheduled_for) },
    { key: 'material', header: t('processedMaterials.batches.columns.material'), render: (r) => (
      <div>
        <p className="font-medium">{r.processed_material_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.processed_material_sku}</p>
      </div>
    )},
    { key: 'batches', header: t('processedMaterials.batches.columns.batches'), align: 'right', render: (r) => formatQuantity(r.batches) },
    { key: 'qty', header: t('processedMaterials.batches.columns.produced'), align: 'right', render: (r) => (
      `${formatQuantity(r.quantity_produced)} ${r.processed_material_unit}`
    )},
    { key: 'cost', header: t('processedMaterials.batches.columns.cost'), align: 'right', render: (r) => formatMoney(r.cost) },
    { key: 'when', header: t('processedMaterials.batches.columns.completed'), render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
    { key: 'by', header: t('processedMaterials.batches.columns.by'), render: (r) => r.created_by_name ?? '—' },
  ];

  const exportColumns: ExportColumn<ProcessedMaterialBatch>[] = [
    { key: 'scheduled_for', header: t('processedMaterials.batches.exportCols.scheduled'), value: (r) => r.scheduled_for },
    { key: 'completed_at', header: t('processedMaterials.batches.exportCols.completed'), value: (r) => r.completed_at ?? '' },
    { key: 'processed_material_sku', header: t('processedMaterials.batches.exportCols.materialSku'), value: (r) => r.processed_material_sku },
    { key: 'processed_material_name', header: t('processedMaterials.batches.exportCols.material'), value: (r) => r.processed_material_name },
    { key: 'batches', header: t('processedMaterials.batches.exportCols.batches'), value: (r) => Number(r.batches) },
    { key: 'quantity_produced', header: t('processedMaterials.batches.exportCols.produced'), value: (r) => Number(r.quantity_produced) },
    { key: 'processed_material_unit', header: t('processedMaterials.batches.exportCols.unit'), value: (r) => r.processed_material_unit },
    { key: 'cost', header: t('processedMaterials.batches.exportCols.cost'), value: (r) => Number(r.cost) },
    { key: 'created_by', header: t('processedMaterials.batches.exportCols.by'), value: (r) => r.created_by_name ?? '' },
    { key: 'notes', header: t('processedMaterials.batches.exportCols.notes'), value: (r) => r.notes },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('processedMaterials.batches.searchPlaceholder')} />
        <ExportMenu
          filename="processed-batches"
          columns={exportColumns}
          fetchRows={() => fetchAllPaginated(
            (p) => processedMaterials.batches.list(p),
            list.search ? { search: list.search } : {},
          )}
        />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState
          icon={PlayCircle}
          title={t('processedMaterials.batches.emptyTitle')}
          description={t('processedMaterials.batches.emptyDescription')}
        />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}
    </>
  );
}

// ── Movements tab ─────────────────────────────────────────────────────────
function MovementsTab() {
  const { t } = useTranslation();
  const list = useCrudList<ProcessedMaterialStockMovement>({
    queryKey: ['processed-movements'],
    fetcher: (p) => processedMaterials.movements.list(p),
  });

  const columns: Column<ProcessedMaterialStockMovement>[] = [
    { key: 'when', header: t('processedMaterials.movements.columns.when'), render: (r) => formatDateTime(r.created_at) },
    { key: 'item', header: t('processedMaterials.movements.columns.material'), render: (r) => <span className="font-medium">{r.item_name}</span> },
    { key: 'reason', header: t('processedMaterials.movements.columns.reason'), render: (r) => <span className="badge-gray">{r.reason_display}</span> },
    { key: 'delta', header: t('processedMaterials.movements.columns.delta'), align: 'right', render: (r) => (
      <span className={Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
        {Number(r.quantity_delta) > 0 ? '+' : ''}{formatQuantity(r.quantity_delta)} {r.item_unit}
      </span>
    )},
    { key: 'balance', header: t('processedMaterials.movements.columns.after'), align: 'right', render: (r) => (
      `${formatQuantity(r.balance_after)} ${r.item_unit}`
    )},
    { key: 'ref', header: t('processedMaterials.movements.columns.ref'), render: (r) => <span className="font-mono text-xs">{r.reference || '—'}</span> },
    { key: 'who', header: t('processedMaterials.movements.columns.by'), render: (r) => r.created_by_name ?? '—' },
  ];

  const exportColumns: ExportColumn<ProcessedMaterialStockMovement>[] = [
    { key: 'created_at', header: t('processedMaterials.movements.exportCols.when'), value: (r) => r.created_at },
    { key: 'item_sku', header: t('processedMaterials.movements.exportCols.sku'), value: (r) => r.item_sku },
    { key: 'item_name', header: t('processedMaterials.movements.exportCols.material'), value: (r) => r.item_name },
    { key: 'item_unit', header: t('processedMaterials.movements.exportCols.unit'), value: (r) => r.item_unit },
    { key: 'reason', header: t('processedMaterials.movements.exportCols.reason'), value: (r) => r.reason_display },
    { key: 'quantity_delta', header: t('processedMaterials.movements.exportCols.quantityDelta'), value: (r) => Number(r.quantity_delta) },
    { key: 'balance_after', header: t('processedMaterials.movements.exportCols.balanceAfter'), value: (r) => Number(r.balance_after) },
    { key: 'reference', header: t('processedMaterials.movements.exportCols.reference'), value: (r) => r.reference },
    { key: 'note', header: t('processedMaterials.movements.exportCols.note'), value: (r) => r.note },
    { key: 'created_by', header: t('processedMaterials.movements.exportCols.by'), value: (r) => r.created_by_name ?? '' },
  ];

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-end">
        <ExportMenu
          filename="processed-movements"
          columns={exportColumns}
          fetchRows={() => fetchAllPaginated((p) => processedMaterials.movements.list(p))}
        />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={History} title={t('processedMaterials.movements.emptyTitle')} />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}
    </>
  );
}
