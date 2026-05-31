import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Package, Layers, X } from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';
import { catalog } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { processedMaterials as processedMaterialsApi } from '@/api/processed-materials';
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
import { formatMoney, formatNumber } from '@/lib/format';
const empty = {
    sku: '', name: '', category: '', description: '', unit: 'unit',
    selling_price: '0', overhead_pct: '0', reorder_threshold: 10, is_active: true,
};
export function ProductsPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['products'],
        fetcher: (p) => catalog.products.list(p),
        deleter: (id) => catalog.products.remove(id),
    });
    const categories = useQuery({ queryKey: ['categories-all'], queryFn: () => catalog.categories.list({ page_size: 200 }) });
    const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
    const materials = useQuery({ queryKey: ['materials-all'], queryFn: () => catalog.rawMaterials.list({ page_size: 500 }) });
    const processed = useQuery({ queryKey: ['processed-materials-all'], queryFn: () => processedMaterialsApi.list({ page_size: 500 }) });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(empty);
    const [toDelete, setToDelete] = useState(null);
    const [recipeOpen, setRecipeOpen] = useState(null);
    const [newCategoryName, setNewCategoryName] = useState('');
    const [addingCategory, setAddingCategory] = useState(false);
    const createCategory = useMutation({
        mutationFn: (name) => catalog.categories.create({ name }),
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
        mutationFn: () => editing ? catalog.products.update(editing.id, form) : catalog.products.create(form),
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
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'sku', header: t('products.columns.sku'), render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.sku }) },
        { key: 'name', header: t('products.columns.name'), render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'cat', header: t('products.columns.category'), render: (r) => _jsx("span", { className: "badge-gray", children: r.category_name }) },
        { key: 'price', header: t('products.columns.price'), align: 'right', render: (r) => formatMoney(r.selling_price) },
        { key: 'cost', header: t('products.columns.cost'), align: 'right', render: (r) => formatMoney(r.production_cost) },
        { key: 'margin', header: t('products.columns.margin'), align: 'right', render: (r) => (_jsx("span", { className: "font-medium text-emerald-700", children: formatMoney(r.margin ?? 0) })) },
        { key: 'status', header: '', render: (r) => (r.is_active
                ? _jsx("span", { className: "badge-green", children: t('common.active') })
                : _jsx("span", { className: "badge-gray", children: t('common.off') })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5 text-brand-700", title: t('products.recipe.title', { name: r.name }), onClick: (e) => { e.stopPropagation(); setRecipeOpen(r); }, children: _jsx(Layers, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
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
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('products.title'), subtitle: t('products.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "products", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => catalog.products.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('products.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('products.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Package, title: t('products.emptyTitle'), description: t('products.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => { setOpen(false); setAddingCategory(false); setNewCategoryName(''); }, title: editing ? t('products.edit') : t('products.new'), size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => { setOpen(false); setAddingCategory(false); setNewCategoryName(''); }, children: t('common.cancel') }), _jsx("button", { className: "btn-primary", onClick: () => save.mutate(), disabled: save.isPending || !form.name || !form.sku || !form.category, children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('products.fields.sku') }), _jsx("input", { className: "input font-mono", value: form.sku ?? '', onChange: (e) => setForm({ ...form, sku: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('products.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("label", { className: "label", children: t('products.fields.category') }), !addingCategory && (_jsx("button", { type: "button", className: "text-xs text-brand-700 hover:underline", onClick: () => setAddingCategory(true), children: t('products.fields.newCategory') }))] }), addingCategory ? (_jsxs("div", { className: "flex gap-2", children: [_jsx("input", { className: "input", autoFocus: true, placeholder: t('products.fields.newCategoryNamePlaceholder'), value: newCategoryName, onChange: (e) => setNewCategoryName(e.target.value), onKeyDown: (e) => {
                                                if (e.key === 'Enter' && newCategoryName.trim()) {
                                                    e.preventDefault();
                                                    createCategory.mutate(newCategoryName.trim());
                                                }
                                            } }), _jsx("button", { type: "button", className: "btn-primary px-3", disabled: !newCategoryName.trim() || createCategory.isPending, onClick: () => createCategory.mutate(newCategoryName.trim()), children: createCategory.isPending ? '…' : t('common.add') }), _jsx("button", { type: "button", className: "btn-secondary px-3", onClick: () => { setAddingCategory(false); setNewCategoryName(''); }, children: t('common.cancel') })] })) : (_jsxs("select", { className: "input", value: form.category ?? '', onChange: (e) => setForm({ ...form, category: e.target.value }), children: [_jsx("option", { value: "", children: t('common.select') }), categories.data?.results.map((c) => _jsx("option", { value: c.id, children: c.name }, c.id))] })), !addingCategory && categories.data && categories.data.results.length === 0 && (_jsx("p", { className: "text-xs text-amber-600 mt-1", children: t('products.fields.noCategoriesHint') }))] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('products.fields.unit') }), _jsx("select", { className: "input", value: form.unit ?? 'unit', onChange: (e) => setForm({ ...form, unit: e.target.value }), children: units.data?.map((u) => _jsx("option", { value: u.value, children: u.label }, u.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('products.fields.sellingPrice') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.selling_price ?? '0', onChange: (e) => setForm({ ...form, selling_price: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('products.fields.reorderThreshold') }), _jsx("input", { type: "number", className: "input", value: form.reorder_threshold ?? 0, onChange: (e) => setForm({ ...form, reorder_threshold: Number(e.target.value) }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('products.fields.description') }), _jsx("textarea", { className: "input", rows: 2, value: form.description ?? '', onChange: (e) => setForm({ ...form, description: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-prod", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-prod", className: "text-sm", children: t('products.fields.active') })] })] }) }), _jsx(RecipeModal, { open: !!recipeOpen, product: recipeOpen, materials: materials.data?.results ?? [], processedMaterials: processed.data?.results ?? [], onClose: () => setRecipeOpen(null) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('products.deleteTitle'), message: t('products.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
function RecipeModal({ open, product: productProp, materials, processedMaterials, onClose, }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
    // Track live product data (overhead_pct, production_cost) so the modal
    // reflects edits without needing a parent reopen.
    const productQuery = useQuery({
        queryKey: ['product', productProp?.id],
        queryFn: () => catalog.products.get(productProp.id),
        enabled: !!productProp,
    });
    const product = productQuery.data ?? productProp;
    const recipeQuery = useQuery({
        queryKey: ['recipes', product?.id],
        queryFn: () => catalog.recipes.list({ product: product.id, page_size: 200 }),
        enabled: !!product,
    });
    const usagesQuery = useQuery({
        queryKey: ['processed-usages', product?.id],
        queryFn: () => processedMaterialsApi.usages.list({ product: product.id, page_size: 200 }),
        enabled: !!product,
    });
    // Encoded as "raw:<id>" or "processed:<id>" so a single dropdown can pick either kind.
    const [newSelection, setNewSelection] = useState('');
    const [newQty, setNewQty] = useState('');
    // Local-edited overhead %, synced from the product prop whenever it changes.
    const [overheadPct, setOverheadPct] = useState(product?.overhead_pct ?? '0');
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
                    product: product.id, processed_material: id, quantity: newQty,
                });
            }
            return catalog.recipes.create({
                product: product.id, raw_material: id, quantity: newQty,
            });
        },
        onSuccess: () => {
            toast.success(t('products.recipe.added'));
            invalidateAll();
            setNewSelection('');
            setNewQty('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const deleteRaw = useMutation({
        mutationFn: (id) => catalog.recipes.remove(id),
        onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
    });
    const deleteProcessed = useMutation({
        mutationFn: (id) => processedMaterialsApi.usages.remove(id),
        onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
    });
    const saveOverhead = useMutation({
        mutationFn: (pct) => catalog.products.update(product.id, { overhead_pct: pct }),
        onSuccess: () => { toast.success(t('products.recipe.overheadSaved')); invalidateAll(); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const rawItems = recipeQuery.data?.results ?? [];
    const usageItems = usagesQuery.data?.results ?? [];
    const rows = [
        ...rawItems.map((it) => ({
            kind: 'raw', id: it.id, name: it.raw_material_name ?? '',
            unit: it.raw_material_unit, quantity: it.quantity,
            lineCost: Number(it.quantity) * Number(it.raw_material_unit_cost ?? 0),
        })),
        ...usageItems.map((u) => ({
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
    return (_jsxs(Modal, { open: open, onClose: onClose, title: t('products.recipe.title', { name: product?.name ?? '' }), size: "lg", children: [_jsx("p", { className: "text-sm text-slate-500 mb-4", children: _jsx(Trans, { i18nKey: "products.recipe.lead", components: { 1: _jsx("strong", {}) } }) }), _jsxs("div", { className: "grid grid-cols-12 gap-2 mb-2 px-3 text-xs uppercase tracking-wider text-slate-500", children: [_jsx("span", { className: "col-span-6", children: t('products.recipe.material') }), _jsx("span", { className: "col-span-3 text-right", children: t('products.recipe.quantity') }), _jsx("span", { className: "col-span-2 text-right", children: t('products.recipe.cost') }), _jsx("span", { className: "col-span-1" })] }), _jsxs("ul", { className: "divide-y divide-slate-100 border border-slate-200 rounded-md", children: [rows.map((r) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsxs("span", { className: "col-span-6 text-sm flex items-center gap-2", children: [_jsx("span", { className: r.kind === 'processed' ? 'badge-blue' : 'badge-gray', children: r.kind === 'processed' ? t('products.recipe.processed') : t('products.recipe.raw') }), r.name] }), _jsxs("span", { className: "col-span-3 text-right text-sm", children: [formatNumber(r.quantity, 2), " ", r.unit] }), _jsx("span", { className: "col-span-2 text-right text-sm text-slate-600", children: formatMoney(r.lineCost) }), _jsx("button", { className: "col-span-1 text-red-500 hover:text-red-700 justify-self-end", onClick: () => (r.kind === 'processed' ? deleteProcessed : deleteRaw).mutate(r.id), children: _jsx(X, { size: 16 }) })] }, `${r.kind}:${r.id}`))), rows.length === 0 && (_jsx("li", { className: "px-3 py-6 text-center text-sm text-slate-400", children: t('products.recipe.empty') }))] }), _jsxs("div", { className: "grid grid-cols-12 gap-2 mt-4 items-end", children: [_jsxs("div", { className: "col-span-7", children: [_jsx("label", { className: "label", children: t('products.recipe.addMaterial') }), _jsxs("select", { className: "input", value: newSelection, onChange: (e) => setNewSelection(e.target.value), children: [_jsx("option", { value: "", children: t('common.select') }), _jsx("optgroup", { label: t('products.recipe.rawMaterials'), children: materials.map((m) => (_jsxs("option", { value: `raw:${m.id}`, children: [m.name, " (", m.unit, ")"] }, `raw:${m.id}`))) }), _jsx("optgroup", { label: t('products.recipe.processedMaterials'), children: processedMaterials.map((p) => (_jsxs("option", { value: `processed:${p.id}`, children: [p.name, " (", p.unit, ")"] }, `processed:${p.id}`))) })] })] }), _jsxs("div", { className: "col-span-4", children: [_jsx("label", { className: "label", children: t('products.recipe.quantity') }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: newQty, onChange: (e) => setNewQty(e.target.value) })] }), _jsx("button", { className: "col-span-1 btn-primary px-2 py-2", disabled: !newSelection || !newQty || addItem.isPending, onClick: () => addItem.mutate(), "aria-label": t('common.add'), children: _jsx(Plus, { size: 16 }) })] }), _jsxs("div", { className: "mt-6 border-t border-slate-200 pt-4 space-y-2", children: [_jsxs("div", { className: "flex items-center justify-between text-sm", children: [_jsx("span", { className: "text-slate-600", children: t('products.recipe.ingredientSubtotal') }), _jsx("span", { className: "font-medium tabular-nums", children: formatMoney(ingredientCost) })] }), _jsxs("div", { className: "grid grid-cols-12 gap-2 items-center", children: [_jsx("label", { className: "col-span-6 text-sm text-slate-600", htmlFor: "overhead-pct", children: t('products.recipe.overheadLabel') }), _jsx("div", { className: "col-span-3", children: _jsx("input", { id: "overhead-pct", type: "number", step: "0.01", min: "0", className: "input text-right", value: overheadPct, onChange: (e) => setOverheadPct(e.target.value), disabled: !product }) }), _jsx("span", { className: "col-span-3 text-right text-sm font-medium tabular-nums text-slate-700", children: formatMoney(overheadAmount) })] }), overheadDirty && (_jsxs("div", { className: "flex justify-end gap-2", children: [_jsx("button", { type: "button", className: "btn-secondary text-xs px-2 py-1", onClick: () => setOverheadPct(product?.overhead_pct ?? '0'), disabled: saveOverhead.isPending, children: t('common.reset') }), _jsx("button", { type: "button", className: "btn-primary text-xs px-2 py-1", onClick: () => saveOverhead.mutate(overheadPct), disabled: saveOverhead.isPending, children: saveOverhead.isPending ? t('common.saving') : t('products.recipe.saveOverhead') })] })), _jsxs("div", { className: "flex items-center justify-between border-t border-slate-200 pt-2 text-sm", children: [_jsx("span", { className: "font-medium text-slate-800", children: t('products.recipe.totalCost') }), _jsx("span", { className: "font-semibold text-slate-900 tabular-nums", children: formatMoney(totalCost) })] })] })] }));
}
