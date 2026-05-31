import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Package, Layers, X } from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';

import { catalog } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { processedMaterials as processedMaterialsApi } from '@/api/processed-materials';
import type { ProcessedMaterial, ProcessedUsage } from '@/api/processed-materials';
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
import type { Product, RawMaterial, RecipeItem } from '@/api/types';

const empty: Partial<Product> = {
  sku: '', name: '', category: '', description: '', unit: 'unit',
  selling_price: '0', overhead_pct: '0', reorder_threshold: 10, is_active: true,
};

export function ProductsPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Product>({
    queryKey: ['products'],
    fetcher: (p) => catalog.products.list(p),
    deleter: (id) => catalog.products.remove(id),
  });

  const categories = useQuery({ queryKey: ['categories-all'], queryFn: () => catalog.categories.list({ page_size: 200 }) });
  const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
  const materials = useQuery({ queryKey: ['materials-all'], queryFn: () => catalog.rawMaterials.list({ page_size: 500 }) });
  const processed = useQuery({ queryKey: ['processed-materials-all'], queryFn: () => processedMaterialsApi.list({ page_size: 500 }) });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<Partial<Product>>(empty);
  const [toDelete, setToDelete] = useState<Product | null>(null);
  const [recipeOpen, setRecipeOpen] = useState<Product | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [addingCategory, setAddingCategory] = useState(false);

  const createCategory = useMutation({
    mutationFn: (name: string) => catalog.categories.create({ name }),
    onSuccess: async (created) => {
      toast.success(t('products.categoryCreated', { name: created.name }));
      await qc.invalidateQueries({ queryKey: ['categories-all'] });
      setForm((f) => ({ ...f, category: created.id }));
      setNewCategoryName('');
      setAddingCategory(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const save = useMutation({
    mutationFn: () =>
      editing ? catalog.products.update(editing.id, form) : catalog.products.create(form),
    onSuccess: () => {
      toast.success(editing ? t('products.updated') : t('products.created'));
      qc.invalidateQueries({ queryKey: ['products'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    const firstCategory = categories.data?.results[0]?.id ?? '';
    setEditing(null);
    setForm({ ...empty, category: firstCategory });
    setOpen(true);
  }
  function openEdit(row: Product) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<Product>[] = [
    { key: 'sku', header: t('products.columns.sku'), render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
    { key: 'name', header: t('products.columns.name'), render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'cat', header: t('products.columns.category'), render: (r) => <span className="badge-gray">{r.category_name}</span> },
    { key: 'price', header: t('products.columns.price'), align: 'right', render: (r) => formatMoney(r.selling_price) },
    { key: 'cost', header: t('products.columns.cost'), align: 'right', render: (r) => formatMoney(r.production_cost) },
    { key: 'margin', header: t('products.columns.margin'), align: 'right', render: (r) => (
      <span className="font-medium text-emerald-700">{formatMoney(r.margin ?? 0)}</span>
    )},
    { key: 'status', header: '', render: (r) => (
      r.is_active
        ? <span className="badge-green">{t('common.active')}</span>
        : <span className="badge-gray">{t('common.off')}</span>
    )},
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5 text-brand-700"
          title={t('products.recipe.title', { name: r.name })}
          onClick={(e) => { e.stopPropagation(); setRecipeOpen(r); }}
        >
          <Layers size={14} />
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

  const exportColumns: ExportColumn<Product>[] = [
    { key: 'sku', header: t('products.exportCols.sku'), value: (r) => r.sku },
    { key: 'name', header: t('products.exportCols.name'), value: (r) => r.name },
    { key: 'category', header: t('products.exportCols.category'), value: (r) => r.category_name ?? '' },
    { key: 'unit', header: t('products.exportCols.unit'), value: (r) => r.unit },
    { key: 'selling_price', header: t('products.exportCols.sellingPrice'), value: (r) => Number(r.selling_price) },
    { key: 'production_cost', header: t('products.exportCols.productionCost'), value: (r) => Number(r.production_cost) },
    { key: 'margin', header: t('products.exportCols.margin'), value: (r) => Number(r.margin ?? 0) },
    { key: 'overhead_pct', header: t('products.exportCols.overheadPct'), value: (r) => Number(r.overhead_pct ?? 0) },
    { key: 'reorder_threshold', header: t('products.exportCols.reorderThreshold'), value: (r) => r.reorder_threshold },
    { key: 'is_active', header: t('products.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    { key: 'description', header: t('products.exportCols.description'), value: (r) => r.description },
  ];

  return (
    <>
      <PageHeader
        title={t('products.title')}
        subtitle={t('products.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="products"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => catalog.products.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={openCreate} className="btn-primary"><Plus size={16} /> {t('products.new')}</button>
          </>
        }
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('products.searchPlaceholder')} />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Package} title={t('products.emptyTitle')} description={t('products.emptyDescription')} />}
        />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open}
        onClose={() => { setOpen(false); setAddingCategory(false); setNewCategoryName(''); }}
        title={editing ? t('products.edit') : t('products.new')}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => { setOpen(false); setAddingCategory(false); setNewCategoryName(''); }}>{t('common.cancel')}</button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending || !form.name || !form.sku || !form.category}>
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">{t('products.fields.sku')}</label>
            <input className="input font-mono" value={form.sku ?? ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('products.fields.name')}</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="label">{t('products.fields.category')}</label>
              {!addingCategory && (
                <button
                  type="button"
                  className="text-xs text-brand-700 hover:underline"
                  onClick={() => setAddingCategory(true)}
                >
                  {t('products.fields.newCategory')}
                </button>
              )}
            </div>
            {addingCategory ? (
              <div className="flex gap-2">
                <input
                  className="input"
                  autoFocus
                  placeholder={t('products.fields.newCategoryNamePlaceholder')}
                  value={newCategoryName}
                  onChange={(e) => setNewCategoryName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newCategoryName.trim()) {
                      e.preventDefault();
                      createCategory.mutate(newCategoryName.trim());
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn-primary px-3"
                  disabled={!newCategoryName.trim() || createCategory.isPending}
                  onClick={() => createCategory.mutate(newCategoryName.trim())}
                >
                  {createCategory.isPending ? '…' : t('common.add')}
                </button>
                <button
                  type="button"
                  className="btn-secondary px-3"
                  onClick={() => { setAddingCategory(false); setNewCategoryName(''); }}
                >
                  {t('common.cancel')}
                </button>
              </div>
            ) : (
              <select className="input" value={form.category ?? ''} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="">{t('common.select')}</option>
                {categories.data?.results.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
            {!addingCategory && categories.data && categories.data.results.length === 0 && (
              <p className="text-xs text-amber-600 mt-1">
                {t('products.fields.noCategoriesHint')}
              </p>
            )}
          </div>
          <div>
            <label className="label">{t('products.fields.unit')}</label>
            <select className="input" value={form.unit ?? 'unit'} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              {units.data?.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t('products.fields.sellingPrice')}</label>
            <input type="number" step="0.01" className="input" value={form.selling_price ?? '0'} onChange={(e) => setForm({ ...form, selling_price: e.target.value })} />
          </div>
          <div>
            <label className="label">{t('products.fields.reorderThreshold')}</label>
            <input type="number" className="input" value={form.reorder_threshold ?? 0} onChange={(e) => setForm({ ...form, reorder_threshold: Number(e.target.value) })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t('products.fields.description')}</label>
            <textarea className="input" rows={2} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-prod" type="checkbox" checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-prod" className="text-sm">{t('products.fields.active')}</label>
          </div>
        </div>
      </Modal>

      <RecipeModal
        open={!!recipeOpen}
        product={recipeOpen}
        materials={materials.data?.results ?? []}
        processedMaterials={processed.data?.results ?? []}
        onClose={() => setRecipeOpen(null)}
      />

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('products.deleteTitle')}
        message={t('products.deleteMessage', { name: toDelete?.name ?? '' })}
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

type RecipeRow =
  | { kind: 'raw'; id: string; name: string; unit?: string; quantity: string; lineCost: number }
  | { kind: 'processed'; id: string; name: string; unit?: string; quantity: string; lineCost: number };

function RecipeModal({
  open, product: productProp, materials, processedMaterials, onClose,
}: {
  open: boolean;
  product: Product | null;
  materials: RawMaterial[];
  processedMaterials: ProcessedMaterial[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  // Track live product data (overhead_pct, production_cost) so the modal
  // reflects edits without needing a parent reopen.
  const productQuery = useQuery({
    queryKey: ['product', productProp?.id],
    queryFn: () => catalog.products.get(productProp!.id),
    enabled: !!productProp,
  });
  const product = productQuery.data ?? productProp;
  const recipeQuery = useQuery({
    queryKey: ['recipes', product?.id],
    queryFn: () => catalog.recipes.list({ product: product!.id, page_size: 200 }),
    enabled: !!product,
  });
  const usagesQuery = useQuery({
    queryKey: ['processed-usages', product?.id],
    queryFn: () => processedMaterialsApi.usages.list({ product: product!.id, page_size: 200 }),
    enabled: !!product,
  });
  // Encoded as "raw:<id>" or "processed:<id>" so a single dropdown can pick either kind.
  const [newSelection, setNewSelection] = useState('');
  const [newQty, setNewQty] = useState('');
  // Local-edited overhead %, synced from the product prop whenever it changes.
  const [overheadPct, setOverheadPct] = useState<string>(product?.overhead_pct ?? '0');
  useEffect(() => { setOverheadPct(product?.overhead_pct ?? '0'); }, [product?.id, product?.overhead_pct]);

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['recipes', product?.id] });
    qc.invalidateQueries({ queryKey: ['processed-usages', product?.id] });
    qc.invalidateQueries({ queryKey: ['product', product?.id] });
    qc.invalidateQueries({ queryKey: ['products'] });
  };

  const addItem = useMutation({
    mutationFn: async () => {
      const [kind, id] = newSelection.split(':');
      if (kind === 'processed') {
        return processedMaterialsApi.usages.create({
          product: product!.id, processed_material: id, quantity: newQty,
        });
      }
      return catalog.recipes.create({
        product: product!.id, raw_material: id, quantity: newQty,
      });
    },
    onSuccess: () => {
      toast.success(t('products.recipe.added'));
      invalidateAll();
      setNewSelection(''); setNewQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });
  const deleteRaw = useMutation({
    mutationFn: (id: string) => catalog.recipes.remove(id),
    onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
  });
  const deleteProcessed = useMutation({
    mutationFn: (id: string) => processedMaterialsApi.usages.remove(id),
    onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
  });
  const saveOverhead = useMutation({
    mutationFn: (pct: string) => catalog.products.update(product!.id, { overhead_pct: pct }),
    onSuccess: () => { toast.success(t('products.recipe.overheadSaved')); invalidateAll(); },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const rawItems: RecipeItem[] = recipeQuery.data?.results ?? [];
  const usageItems: ProcessedUsage[] = usagesQuery.data?.results ?? [];
  const rows: RecipeRow[] = [
    ...rawItems.map((it): RecipeRow => ({
      kind: 'raw', id: it.id, name: it.raw_material_name ?? '',
      unit: it.raw_material_unit, quantity: it.quantity,
      lineCost: Number(it.quantity) * Number(it.raw_material_unit_cost ?? 0),
    })),
    ...usageItems.map((u): RecipeRow => ({
      kind: 'processed', id: u.id, name: u.processed_material_name ?? '',
      unit: u.processed_material_unit, quantity: u.quantity,
      lineCost: Number(u.quantity) * Number(u.processed_material_unit_cost ?? 0),
    })),
  ];

  const ingredientCost = rows.reduce((sum, r) => sum + r.lineCost, 0);
  const overheadNum = Number(overheadPct) || 0;
  const overheadAmount = ingredientCost * overheadNum / 100;
  const totalCost = ingredientCost + overheadAmount;
  const overheadDirty = product != null
    && Number(overheadPct || 0) !== Number(product.overhead_pct ?? 0);

  return (
    <Modal open={open} onClose={onClose} title={t('products.recipe.title', { name: product?.name ?? '' })} size="lg">
      <p className="text-sm text-slate-500 mb-4">
        <Trans i18nKey="products.recipe.lead" components={{ 1: <strong /> }} />
      </p>
      <div className="grid grid-cols-12 gap-2 mb-2 px-3 text-xs uppercase tracking-wider text-slate-500">
        <span className="col-span-6">{t('products.recipe.material')}</span>
        <span className="col-span-3 text-right">{t('products.recipe.quantity')}</span>
        <span className="col-span-2 text-right">{t('products.recipe.cost')}</span>
        <span className="col-span-1" />
      </div>
      <ul className="divide-y divide-slate-100 border border-slate-200 rounded-md">
        {rows.map((r) => (
          <li key={`${r.kind}:${r.id}`} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
            <span className="col-span-6 text-sm flex items-center gap-2">
              <span className={r.kind === 'processed' ? 'badge-blue' : 'badge-gray'}>
                {r.kind === 'processed' ? t('products.recipe.processed') : t('products.recipe.raw')}
              </span>
              {r.name}
            </span>
            <span className="col-span-3 text-right text-sm">
              {formatNumber(r.quantity, 2)} {r.unit}
            </span>
            <span className="col-span-2 text-right text-sm text-slate-600">
              {formatMoney(r.lineCost)}
            </span>
            <button
              className="col-span-1 text-red-500 hover:text-red-700 justify-self-end"
              onClick={() => (r.kind === 'processed' ? deleteProcessed : deleteRaw).mutate(r.id)}
            >
              <X size={16} />
            </button>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">{t('products.recipe.empty')}</li>
        )}
      </ul>

      <div className="grid grid-cols-12 gap-2 mt-4 items-end">
        <div className="col-span-7">
          <label className="label">{t('products.recipe.addMaterial')}</label>
          <select className="input" value={newSelection} onChange={(e) => setNewSelection(e.target.value)}>
            <option value="">{t('common.select')}</option>
            <optgroup label={t('products.recipe.rawMaterials')}>
              {materials.map((m) => (
                <option key={`raw:${m.id}`} value={`raw:${m.id}`}>{m.name} ({m.unit})</option>
              ))}
            </optgroup>
            <optgroup label={t('products.recipe.processedMaterials')}>
              {processedMaterials.map((p) => (
                <option key={`processed:${p.id}`} value={`processed:${p.id}`}>{p.name} ({p.unit})</option>
              ))}
            </optgroup>
          </select>
        </div>
        <div className="col-span-4">
          <label className="label">{t('products.recipe.quantity')}</label>
          <input type="number" step="0.0001" className="input" value={newQty} onChange={(e) => setNewQty(e.target.value)} />
        </div>
        <button
          className="col-span-1 btn-primary px-2 py-2"
          disabled={!newSelection || !newQty || addItem.isPending}
          onClick={() => addItem.mutate()}
          aria-label={t('common.add')}
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="mt-6 border-t border-slate-200 pt-4 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600">{t('products.recipe.ingredientSubtotal')}</span>
          <span className="font-medium tabular-nums">{formatMoney(ingredientCost)}</span>
        </div>
        <div className="grid grid-cols-12 gap-2 items-center">
          <label className="col-span-6 text-sm text-slate-600" htmlFor="overhead-pct">
            {t('products.recipe.overheadLabel')}
          </label>
          <div className="col-span-3">
            <input
              id="overhead-pct"
              type="number"
              step="0.01"
              min="0"
              className="input text-right"
              value={overheadPct}
              onChange={(e) => setOverheadPct(e.target.value)}
              disabled={!product}
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
              onClick={() => setOverheadPct(product?.overhead_pct ?? '0')}
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
              {saveOverhead.isPending ? t('common.saving') : t('products.recipe.saveOverhead')}
            </button>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 pt-2 text-sm">
          <span className="font-medium text-slate-800">{t('products.recipe.totalCost')}</span>
          <span className="font-semibold text-slate-900 tabular-nums">{formatMoney(totalCost)}</span>
        </div>
      </div>
    </Modal>
  );
}
