import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Pencil, Trash2, Layers, X, ChefHat, PlayCircle, History, Sliders,
} from 'lucide-react';
import { toast } from 'sonner';

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
import { formatDate, formatDateTime, formatMoney, formatNumber } from '@/lib/format';

type Tab = 'materials' | 'batches' | 'movements';

export function ProcessedMaterialsPage() {
  const [tab, setTab] = useState<Tab>('materials');

  return (
    <>
      <PageHeader
        title="Processed materials"
        subtitle="Pre-made components — pizza dough, batters, ganache, pastry cream — produced from raw materials and used in product recipes."
      />

      <div className="card">
        <div className="card-header gap-2 flex-wrap">
          <div className="flex gap-1">
            {([
              { key: 'materials', label: 'Materials', icon: ChefHat },
              { key: 'batches', label: 'Batches', icon: PlayCircle },
              { key: 'movements', label: 'Movements', icon: History },
            ] as { key: Tab; label: string; icon: typeof ChefHat }[]).map(({ key, label, icon: Icon }) => (
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

  // Adjust + produce
  const [adjustFor, setAdjustFor] = useState<ProcessedMaterial | null>(null);
  const [produceFor, setProduceFor] = useState<ProcessedMaterial | null>(null);

  const save = useMutation({
    mutationFn: () =>
      editing ? processedMaterials.update(editing.id, form) : processedMaterials.create(form),
    onSuccess: () => {
      toast.success(editing ? 'Updated.' : 'Created.');
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(emptyMaterial); setOpen(true); }
  function openEdit(row: ProcessedMaterial) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<ProcessedMaterial>[] = [
    { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
    { key: 'name', header: 'Name', render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'unit', header: 'Unit', render: (r) => r.unit },
    { key: 'yield', header: 'Yield/batch', align: 'right', render: (r) => (
      `${formatNumber(r.yield_per_batch)} ${r.unit}`
    )},
    { key: 'cost', header: 'Cost/unit', align: 'right', render: (r) => formatMoney(r.unit_cost) },
    { key: 'stock', header: 'On hand', align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatNumber(r.stock_quantity, 1)} {r.unit}
      </span>
    )},
    { key: 'status', header: '', render: (r) => (
      r.is_low ? <span className="badge-red">Low</span> : <span className="badge-green">OK</span>
    )},
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5 text-emerald-700"
          title="Produce batch"
          onClick={(e) => { e.stopPropagation(); setProduceFor(r); }}
        >
          <PlayCircle size={14} />
        </button>
        <button
          className="btn-ghost p-1.5 text-brand-700"
          title="Recipe (ingredients)"
          onClick={(e) => { e.stopPropagation(); setRecipeFor(r); }}
        >
          <Layers size={14} />
        </button>
        <button
          className="btn-ghost p-1.5 text-blue-700"
          title="Used in products"
          onClick={(e) => { e.stopPropagation(); setUsageFor(r); }}
        >
          <ChefHat size={14} />
        </button>
        <button
          className="btn-ghost p-1.5"
          title="Adjust stock"
          onClick={(e) => { e.stopPropagation(); setAdjustFor(r); }}
        >
          <Sliders size={14} />
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

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search processed materials…" />
        <button onClick={openCreate} className="btn-primary"><Plus size={16} /> New material</button>
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState
          icon={ChefHat}
          title="No processed materials yet"
          description='Add things like "pizza dough" or "ganache" — pre-made components used inside product recipes.'
        />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}

      {/* CRUD modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? `Edit ${editing.name}` : 'New processed material'}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!form.name || !form.sku || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">SKU</label>
            <input className="input font-mono" value={form.sku ?? ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          </div>
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Unit</label>
            <select className="input" value={form.unit ?? 'g'} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              {units.data?.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Yield per batch</label>
            <input type="number" step="0.01" className="input" value={form.yield_per_batch ?? '1'}
              onChange={(e) => setForm({ ...form, yield_per_batch: e.target.value })} />
          </div>
          <div>
            <label className="label">Shelf life (hours)</label>
            <input type="number" className="input" value={form.shelf_life_hours ?? 24}
              onChange={(e) => setForm({ ...form, shelf_life_hours: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label">Reorder threshold</label>
            <input type="number" step="0.01" className="input" value={form.reorder_threshold ?? '0'}
              onChange={(e) => setForm({ ...form, reorder_threshold: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Notes</label>
            <textarea className="input" rows={2} value={form.notes ?? ''}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-pm" type="checkbox" checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-pm" className="text-sm">Active</label>
          </div>
        </div>
      </Modal>

      <RecipeModal open={!!recipeFor} material={recipeFor} onClose={() => setRecipeFor(null)} />
      <UsageModal open={!!usageFor} material={usageFor} onClose={() => setUsageFor(null)} />
      <AdjustModal material={adjustFor} onClose={() => setAdjustFor(null)} />
      <ProduceModal material={produceFor} onClose={() => setProduceFor(null)} />

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title="Delete processed material?"
        message={`Remove "${toDelete?.name}"? Linked recipes and product usages will also be affected.`}
        confirmLabel="Delete"
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
      toast.success('Recipe line added.');
      invalidateAll();
      setNewIngredient(''); setNewQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => processedMaterials.recipes.remove(id),
    onSuccess: () => { toast.success('Removed.'); invalidateAll(); },
  });
  const saveOverhead = useMutation({
    mutationFn: (pct: string) => processedMaterials.update(material!.id, { overhead_pct: pct }),
    onSuccess: () => { toast.success('Overhead updated.'); invalidateAll(); },
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
      title={`Recipe — ${material?.name ?? ''}`}
      size="lg"
    >
      <p className="text-sm text-slate-500 mb-4">
        Quantities below produce <strong>one batch</strong> (yield = {formatNumber(material?.yield_per_batch ?? 0)} {material?.unit}).
        Ingredients can be raw materials or other processed materials.
      </p>
      <div className="grid grid-cols-12 gap-2 mb-2 px-3 text-xs uppercase tracking-wider text-slate-500">
        <span className="col-span-6">Ingredient</span>
        <span className="col-span-3 text-right">Quantity</span>
        <span className="col-span-2 text-right">Cost</span>
        <span className="col-span-1" />
      </div>
      <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">No ingredients in recipe yet.</li>
        )}
        {rows.map((it) => (
          <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
            <span className="col-span-6 text-sm flex items-center gap-2">
              {it.ingredientName}
              {it.isSub && (
                <span className="badge-gray text-[10px]" title="Processed material (sub-recipe)">
                  processed
                </span>
              )}
            </span>
            <span className="col-span-3 text-right text-sm">
              {formatNumber(it.quantity, 2)} {it.ingredientUnit}
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
          { key: 'raw' as const, label: 'Raw material' },
          { key: 'processed' as const, label: 'Processed material' },
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
            Add {kind === 'raw' ? 'raw material' : 'processed material'}
          </label>
          <select
            className="input"
            value={newIngredient}
            onChange={(e) => setNewIngredient(e.target.value)}
          >
            <option value="">— Select —</option>
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
          <label className="label">Quantity / batch</label>
          <input type="number" step="0.0001" className="input"
            value={newQty} onChange={(e) => setNewQty(e.target.value)} />
        </div>
        <button
          className="col-span-1 btn-primary px-2 py-2"
          disabled={!newIngredient || !newQty || add.isPending}
          onClick={() => add.mutate()}
          aria-label="Add"
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="mt-6 border-t border-slate-200 pt-4 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600">Ingredient subtotal (per batch)</span>
          <span className="font-medium tabular-nums">{formatMoney(ingredientCost)}</span>
        </div>
        <div className="grid grid-cols-12 gap-2 items-center">
          <label className="col-span-6 text-sm text-slate-600" htmlFor="pm-overhead-pct">
            Variable overhead estimate (%)
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
              Reset
            </button>
            <button
              type="button"
              className="btn-primary text-xs px-2 py-1"
              onClick={() => saveOverhead.mutate(overheadPct)}
              disabled={saveOverhead.isPending}
            >
              {saveOverhead.isPending ? 'Saving…' : 'Save overhead'}
            </button>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 pt-2 text-sm">
          <span className="font-medium text-slate-800">Total batch cost</span>
          <span className="font-semibold text-slate-900 tabular-nums">{formatMoney(totalBatchCost)}</span>
        </div>
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            Per unit ({formatNumber(material?.yield_per_batch ?? 0)} {material?.unit}/batch)
          </span>
          <span className="tabular-nums">{formatMoney(perUnitCost)} / {material?.unit ?? 'unit'}</span>
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
      toast.success('Usage added.');
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      setProductId(''); setQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => processedMaterials.usages.remove(id),
    onSuccess: () => {
      toast.success('Removed.');
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
    },
  });

  return (
    <Modal open={open} onClose={onClose}
      title={`Used in products — ${material?.name ?? ''}`}
      size="lg"
    >
      <p className="text-sm text-slate-500 mb-4">
        Quantity per <strong>one unit</strong> of the product. Stock is decremented automatically when a production run is recorded.
      </p>
      <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {items.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">Not used in any product yet.</li>
        )}
        {items.map((it) => (
          <li key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
            <span className="col-span-7 text-sm">{it.product_name}</span>
            <span className="col-span-4 text-right text-sm">
              {formatNumber(it.quantity, 2)} {material?.unit}
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
          <label className="label">Add product</label>
          <select className="input" value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">— Select —</option>
            {products.data?.results.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div className="col-span-4">
          <label className="label">Qty per unit</label>
          <input type="number" step="0.0001" className="input"
            value={qty} onChange={(e) => setQty(e.target.value)} />
        </div>
        <button
          className="col-span-1 btn-primary px-2 py-2"
          disabled={!productId || !qty || add.isPending}
          onClick={() => add.mutate()}
          aria-label="Add"
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
  const [delta, setDelta] = useState('');
  const [note, setNote] = useState('');

  const mutate = useMutation({
    mutationFn: () => processedMaterials.stock.adjust({
      processed_material: material!.id,
      quantity_delta: Number(delta),
      note,
    }),
    onSuccess: () => {
      toast.success('Adjustment recorded.');
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
      title={`Adjust: ${material.name}`}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!delta || Number(delta) === 0 || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending ? 'Saving…' : 'Apply'}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        Current on-hand: <strong>{formatNumber(material.stock_quantity, 2)} {material.unit}</strong>.
        Positive to add, negative to remove (e.g. waste).
      </p>
      <div className="space-y-3">
        <div>
          <label className="label">Delta ({material.unit})</label>
          <input autoFocus type="number" step="0.01" className="input"
            value={delta} onChange={(e) => setDelta(e.target.value)} />
        </div>
        <div>
          <label className="label">Note (optional)</label>
          <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Produce a batch ───────────────────────────────────────────────────────
function ProduceModal({ material, onClose }: { material: ProcessedMaterial | null; onClose: () => void }) {
  const qc = useQueryClient();
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
      toast.success(`Produced ${formatNumber(batch.quantity_produced, 1)} ${material?.unit}.`);
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
      title={`Produce batch — ${material.name}`}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!batches || Number(batches) <= 0 || produce.isPending}
            onClick={() => produce.mutate()}
          >
            {produce.isPending ? 'Producing…' : 'Produce'}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        Each batch yields <strong>{formatNumber(material.yield_per_batch)} {material.unit}</strong>.
        Will produce <strong>{formatNumber(projected, 0)} {material.unit}</strong> and consume raw materials per recipe.
      </p>
      <div className="space-y-3">
        <div>
          <label className="label">Batches</label>
          <input autoFocus type="number" step="0.01" min="0.01" className="input"
            value={batches} onChange={(e) => setBatches(e.target.value)} />
        </div>
        <div>
          <label className="label">Scheduled for</label>
          <input type="date" className="input"
            value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
        </div>
        <div>
          <label className="label">Notes</label>
          <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Batches tab ───────────────────────────────────────────────────────────
function BatchesTab() {
  const list = useCrudList<ProcessedMaterialBatch>({
    queryKey: ['processed-batches'],
    fetcher: (p) => processedMaterials.batches.list(p),
    deleter: (id) => processedMaterials.batches.remove(id),
  });

  const columns: Column<ProcessedMaterialBatch>[] = [
    { key: 'sched', header: 'Scheduled', render: (r) => formatDate(r.scheduled_for) },
    { key: 'material', header: 'Material', render: (r) => (
      <div>
        <p className="font-medium">{r.processed_material_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.processed_material_sku}</p>
      </div>
    )},
    { key: 'batches', header: 'Batches', align: 'right', render: (r) => formatNumber(r.batches, 2) },
    { key: 'qty', header: 'Produced', align: 'right', render: (r) => (
      `${formatNumber(r.quantity_produced, 1)} ${r.processed_material_unit}`
    )},
    { key: 'cost', header: 'Cost', align: 'right', render: (r) => formatMoney(r.cost) },
    { key: 'when', header: 'Completed', render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
    { key: 'by', header: 'By', render: (r) => r.created_by_name ?? '—' },
  ];

  return (
    <>
      <div className="px-5 pt-3">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search batches…" />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState
          icon={PlayCircle}
          title="No batches recorded"
          description="Use the ▶ button on a material to record one."
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
  const list = useCrudList<ProcessedMaterialStockMovement>({
    queryKey: ['processed-movements'],
    fetcher: (p) => processedMaterials.movements.list(p),
  });

  const columns: Column<ProcessedMaterialStockMovement>[] = [
    { key: 'when', header: 'When', render: (r) => formatDateTime(r.created_at) },
    { key: 'item', header: 'Material', render: (r) => <span className="font-medium">{r.item_name}</span> },
    { key: 'reason', header: 'Reason', render: (r) => <span className="badge-gray">{r.reason_display}</span> },
    { key: 'delta', header: 'Δ', align: 'right', render: (r) => (
      <span className={Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
        {Number(r.quantity_delta) > 0 ? '+' : ''}{formatNumber(r.quantity_delta, 2)} {r.item_unit}
      </span>
    )},
    { key: 'balance', header: 'After', align: 'right', render: (r) => (
      `${formatNumber(r.balance_after, 2)} ${r.item_unit}`
    )},
    { key: 'ref', header: 'Ref', render: (r) => <span className="font-mono text-xs">{r.reference || '—'}</span> },
    { key: 'who', header: 'By', render: (r) => r.created_by_name ?? '—' },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={History} title="No movements yet" />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}
    </>
  );
}
