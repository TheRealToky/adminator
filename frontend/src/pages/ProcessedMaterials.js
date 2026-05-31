import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Layers, X, ChefHat, PlayCircle, History, Sliders, } from 'lucide-react';
import { toast } from 'sonner';
import { catalog } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { processedMaterials } from '@/api/processed-materials';
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
import { formatDate, formatDateTime, formatMoney, formatNumber } from '@/lib/format';
export function ProcessedMaterialsPage() {
    const [tab, setTab] = useState('materials');
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Processed materials", subtitle: "Pre-made components \u2014 pizza dough, batters, ganache, pastry cream \u2014 produced from raw materials and used in product recipes." }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header gap-2 flex-wrap", children: _jsx("div", { className: "flex gap-1", children: [
                                { key: 'materials', label: 'Materials', icon: ChefHat },
                                { key: 'batches', label: 'Batches', icon: PlayCircle },
                                { key: 'movements', label: 'Movements', icon: History },
                            ].map(({ key, label, icon: Icon }) => (_jsxs("button", { onClick: () => setTab(key), className: `px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: [_jsx(Icon, { size: 14 }), " ", label] }, key))) }) }), tab === 'materials' && _jsx(MaterialsTab, {}), tab === 'batches' && _jsx(BatchesTab, {}), tab === 'movements' && _jsx(MovementsTab, {})] })] }));
}
// ── Materials tab ─────────────────────────────────────────────────────────
const emptyMaterial = {
    sku: '', name: '', unit: 'g', yield_per_batch: '1000',
    shelf_life_hours: 24, reorder_threshold: '0', notes: '', is_active: true,
};
function MaterialsTab() {
    const qc = useQueryClient();
    const list = useCrudList({
        queryKey: ['processed-materials'],
        fetcher: (p) => processedMaterials.list(p),
        deleter: (id) => processedMaterials.remove(id),
    });
    const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyMaterial);
    const [toDelete, setToDelete] = useState(null);
    // Recipe + usage modals
    const [recipeFor, setRecipeFor] = useState(null);
    const [usageFor, setUsageFor] = useState(null);
    // Adjust + produce
    const [adjustFor, setAdjustFor] = useState(null);
    const [produceFor, setProduceFor] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? processedMaterials.update(editing.id, form) : processedMaterials.create(form),
        onSuccess: () => {
            toast.success(editing ? 'Updated.' : 'Created.');
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() { setEditing(null); setForm(emptyMaterial); setOpen(true); }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'sku', header: 'SKU', render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.sku }) },
        { key: 'name', header: 'Name', render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'unit', header: 'Unit', render: (r) => r.unit },
        { key: 'yield', header: 'Yield/batch', align: 'right', render: (r) => (`${formatNumber(r.yield_per_batch)} ${r.unit}`) },
        { key: 'cost', header: 'Cost/unit', align: 'right', render: (r) => formatMoney(r.unit_cost) },
        { key: 'stock', header: 'On hand', align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatNumber(r.stock_quantity, 1), " ", r.unit] })) },
        { key: 'status', header: '', render: (r) => (r.is_low ? _jsx("span", { className: "badge-red", children: "Low" }) : _jsx("span", { className: "badge-green", children: "OK" })) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5 text-emerald-700", title: "Produce batch", onClick: (e) => { e.stopPropagation(); setProduceFor(r); }, children: _jsx(PlayCircle, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-brand-700", title: "Recipe (ingredients)", onClick: (e) => { e.stopPropagation(); setRecipeFor(r); }, children: _jsx(Layers, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-blue-700", title: "Used in products", onClick: (e) => { e.stopPropagation(); setUsageFor(r); }, children: _jsx(ChefHat, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", title: "Adjust stock", onClick: (e) => { e.stopPropagation(); setAdjustFor(r); }, children: _jsx(Sliders, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'sku', header: 'SKU', value: (r) => r.sku },
        { key: 'name', header: 'Name', value: (r) => r.name },
        { key: 'unit', header: 'Unit', value: (r) => r.unit },
        { key: 'yield_per_batch', header: 'Yield/batch', value: (r) => Number(r.yield_per_batch) },
        { key: 'unit_cost', header: 'Unit cost', value: (r) => Number(r.unit_cost) },
        { key: 'overhead_pct', header: 'Overhead %', value: (r) => Number(r.overhead_pct) },
        { key: 'shelf_life_hours', header: 'Shelf life (h)', value: (r) => r.shelf_life_hours },
        { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
        { key: 'stock_quantity', header: 'On hand', value: (r) => Number(r.stock_quantity) },
        { key: 'is_low', header: 'Low stock', value: (r) => (r.is_low ? 'yes' : 'no') },
        { key: 'is_active', header: 'Active', value: (r) => (r.is_active ? 'yes' : 'no') },
        { key: 'notes', header: 'Notes', value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search processed materials\u2026" }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(ExportMenu, { filename: "processed-materials", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => processedMaterials.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New material"] })] })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: ChefHat, title: "No processed materials yet", description: 'Add things like "pizza dough" or "ganache" \u2014 pre-made components used inside product recipes.' }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? `Edit ${editing.name}` : 'New processed material', size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !form.name || !form.sku || save.isPending, onClick: () => save.mutate(), children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "SKU" }), _jsx("input", { className: "input font-mono", value: form.sku ?? '', onChange: (e) => setForm({ ...form, sku: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Name" }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Unit" }), _jsx("select", { className: "input", value: form.unit ?? 'g', onChange: (e) => setForm({ ...form, unit: e.target.value }), children: units.data?.map((u) => _jsx("option", { value: u.value, children: u.label }, u.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Yield per batch" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.yield_per_batch ?? '1', onChange: (e) => setForm({ ...form, yield_per_batch: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Shelf life (hours)" }), _jsx("input", { type: "number", className: "input", value: form.shelf_life_hours ?? 24, onChange: (e) => setForm({ ...form, shelf_life_hours: Number(e.target.value) }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Reorder threshold" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.reorder_threshold ?? '0', onChange: (e) => setForm({ ...form, reorder_threshold: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: "Notes" }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-pm", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-pm", className: "text-sm", children: "Active" })] })] }) }), _jsx(RecipeModal, { open: !!recipeFor, material: recipeFor, onClose: () => setRecipeFor(null) }), _jsx(UsageModal, { open: !!usageFor, material: usageFor, onClose: () => setUsageFor(null) }), _jsx(AdjustModal, { material: adjustFor, onClose: () => setAdjustFor(null) }), _jsx(ProduceModal, { material: produceFor, onClose: () => setProduceFor(null) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete processed material?", message: `Remove "${toDelete?.name}"? Linked recipes and product usages will also be affected.`, confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
function RecipeModal({ open, material: materialProp, onClose, }) {
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
        queryFn: () => processedMaterials.get(materialProp.id),
        enabled: !!materialProp,
    });
    const material = materialQuery.data ?? materialProp;
    // Fetch the recipe lines on their own query so the list updates live as we
    // add/remove items — the parent list query lags behind the modal.
    const recipeQuery = useQuery({
        queryKey: ['processed-recipes', material?.id],
        queryFn: () => processedMaterials.recipes.list({
            processed_material: material.id, page_size: 200,
        }),
        enabled: !!material,
    });
    const items = recipeQuery.data?.results ?? [];
    const [kind, setKind] = useState('raw');
    const [newIngredient, setNewIngredient] = useState('');
    const [newQty, setNewQty] = useState('');
    const [overheadPct, setOverheadPct] = useState(material?.overhead_pct ?? '0');
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
            processed_material: material.id,
            raw_material: kind === 'raw' ? newIngredient : null,
            sub_processed_material: kind === 'processed' ? newIngredient : null,
            quantity: newQty,
        }),
        onSuccess: () => {
            toast.success('Recipe line added.');
            invalidateAll();
            setNewIngredient('');
            setNewQty('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const remove = useMutation({
        mutationFn: (id) => processedMaterials.recipes.remove(id),
        onSuccess: () => { toast.success('Removed.'); invalidateAll(); },
    });
    const saveOverhead = useMutation({
        mutationFn: (pct) => processedMaterials.update(material.id, { overhead_pct: pct }),
        onSuccess: () => { toast.success('Overhead updated.'); invalidateAll(); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const rows = items.map((it) => {
        const isSub = !!it.sub_processed_material;
        const unitCost = Number(isSub ? it.sub_processed_material_unit_cost : it.raw_material_unit_cost) || 0;
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
    return (_jsxs(Modal, { open: open, onClose: onClose, title: `Recipe — ${material?.name ?? ''}`, size: "lg", children: [_jsxs("p", { className: "text-sm text-slate-500 mb-4", children: ["Quantities below produce ", _jsx("strong", { children: "one batch" }), " (yield = ", formatNumber(material?.yield_per_batch ?? 0), " ", material?.unit, "). Ingredients can be raw materials or other processed materials."] }), _jsxs("div", { className: "grid grid-cols-12 gap-2 mb-2 px-3 text-xs uppercase tracking-wider text-slate-500", children: [_jsx("span", { className: "col-span-6", children: "Ingredient" }), _jsx("span", { className: "col-span-3 text-right", children: "Quantity" }), _jsx("span", { className: "col-span-2 text-right", children: "Cost" }), _jsx("span", { className: "col-span-1" })] }), _jsxs("ul", { className: "divide-y divide-slate-100 border border-slate-200 rounded-md", children: [rows.length === 0 && (_jsx("li", { className: "px-3 py-6 text-center text-sm text-slate-400", children: "No ingredients in recipe yet." })), rows.map((it) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsxs("span", { className: "col-span-6 text-sm flex items-center gap-2", children: [it.ingredientName, it.isSub && (_jsx("span", { className: "badge-gray text-[10px]", title: "Processed material (sub-recipe)", children: "processed" }))] }), _jsxs("span", { className: "col-span-3 text-right text-sm", children: [formatNumber(it.quantity, 2), " ", it.ingredientUnit] }), _jsx("span", { className: "col-span-2 text-right text-sm text-slate-600", children: formatMoney(it.lineCost) }), _jsx("button", { className: "col-span-1 text-red-500 hover:text-red-700 justify-self-end", onClick: () => remove.mutate(it.id), children: _jsx(X, { size: 16 }) })] }, it.id)))] }), _jsx("div", { className: "mt-4 flex gap-1 text-xs", children: ([
                    { key: 'raw', label: 'Raw material' },
                    { key: 'processed', label: 'Processed material' },
                ]).map(({ key, label }) => (_jsx("button", { type: "button", onClick: () => setKind(key), className: `px-2.5 py-1 rounded-md font-medium ${kind === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: label }, key))) }), _jsxs("div", { className: "grid grid-cols-12 gap-2 mt-2 items-end", children: [_jsxs("div", { className: "col-span-7", children: [_jsxs("label", { className: "label", children: ["Add ", kind === 'raw' ? 'raw material' : 'processed material'] }), _jsxs("select", { className: "input", value: newIngredient, onChange: (e) => setNewIngredient(e.target.value), children: [_jsx("option", { value: "", children: "\u2014 Select \u2014" }), kind === 'raw'
                                        ? rawMaterials.data?.results.map((m) => (_jsxs("option", { value: m.id, children: [m.name, " (", m.unit, ")"] }, m.id)))
                                        : processedMaterialsList.data?.results
                                            .filter((m) => m.id !== material?.id)
                                            .map((m) => (_jsxs("option", { value: m.id, children: [m.name, " (", m.unit, ")"] }, m.id)))] })] }), _jsxs("div", { className: "col-span-4", children: [_jsx("label", { className: "label", children: "Quantity / batch" }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: newQty, onChange: (e) => setNewQty(e.target.value) })] }), _jsx("button", { className: "col-span-1 btn-primary px-2 py-2", disabled: !newIngredient || !newQty || add.isPending, onClick: () => add.mutate(), "aria-label": "Add", children: _jsx(Plus, { size: 16 }) })] }), _jsxs("div", { className: "mt-6 border-t border-slate-200 pt-4 space-y-2", children: [_jsxs("div", { className: "flex items-center justify-between text-sm", children: [_jsx("span", { className: "text-slate-600", children: "Ingredient subtotal (per batch)" }), _jsx("span", { className: "font-medium tabular-nums", children: formatMoney(ingredientCost) })] }), _jsxs("div", { className: "grid grid-cols-12 gap-2 items-center", children: [_jsx("label", { className: "col-span-6 text-sm text-slate-600", htmlFor: "pm-overhead-pct", children: "Variable overhead estimate (%)" }), _jsx("div", { className: "col-span-3", children: _jsx("input", { id: "pm-overhead-pct", type: "number", step: "0.01", min: "0", className: "input text-right", value: overheadPct, onChange: (e) => setOverheadPct(e.target.value), disabled: !material }) }), _jsx("span", { className: "col-span-3 text-right text-sm font-medium tabular-nums text-slate-700", children: formatMoney(overheadAmount) })] }), overheadDirty && (_jsxs("div", { className: "flex justify-end gap-2", children: [_jsx("button", { type: "button", className: "btn-secondary text-xs px-2 py-1", onClick: () => setOverheadPct(material?.overhead_pct ?? '0'), disabled: saveOverhead.isPending, children: "Reset" }), _jsx("button", { type: "button", className: "btn-primary text-xs px-2 py-1", onClick: () => saveOverhead.mutate(overheadPct), disabled: saveOverhead.isPending, children: saveOverhead.isPending ? 'Saving…' : 'Save overhead' })] })), _jsxs("div", { className: "flex items-center justify-between border-t border-slate-200 pt-2 text-sm", children: [_jsx("span", { className: "font-medium text-slate-800", children: "Total batch cost" }), _jsx("span", { className: "font-semibold text-slate-900 tabular-nums", children: formatMoney(totalBatchCost) })] }), _jsxs("div", { className: "flex items-center justify-between text-xs text-slate-500", children: [_jsxs("span", { children: ["Per unit (", formatNumber(material?.yield_per_batch ?? 0), " ", material?.unit, "/batch)"] }), _jsxs("span", { className: "tabular-nums", children: [formatMoney(perUnitCost), " / ", material?.unit ?? 'unit'] })] })] })] }));
}
// ── Usage modal (products that use this processed material) ──────────────
function UsageModal({ open, material, onClose, }) {
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
            processed_material: material.id,
            quantity: qty,
        }),
        onSuccess: () => {
            toast.success('Usage added.');
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
            setProductId('');
            setQty('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const remove = useMutation({
        mutationFn: (id) => processedMaterials.usages.remove(id),
        onSuccess: () => {
            toast.success('Removed.');
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
        },
    });
    return (_jsxs(Modal, { open: open, onClose: onClose, title: `Used in products — ${material?.name ?? ''}`, size: "lg", children: [_jsxs("p", { className: "text-sm text-slate-500 mb-4", children: ["Quantity per ", _jsx("strong", { children: "one unit" }), " of the product. Stock is decremented automatically when a production run is recorded."] }), _jsxs("ul", { className: "divide-y divide-slate-100 border border-slate-200 rounded-md", children: [items.length === 0 && (_jsx("li", { className: "px-3 py-6 text-center text-sm text-slate-400", children: "Not used in any product yet." })), items.map((it) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsx("span", { className: "col-span-7 text-sm", children: it.product_name }), _jsxs("span", { className: "col-span-4 text-right text-sm", children: [formatNumber(it.quantity, 2), " ", material?.unit] }), _jsx("button", { className: "col-span-1 text-red-500 hover:text-red-700 justify-self-end", onClick: () => remove.mutate(it.id), children: _jsx(X, { size: 16 }) })] }, it.id)))] }), _jsxs("div", { className: "grid grid-cols-12 gap-2 mt-4 items-end", children: [_jsxs("div", { className: "col-span-7", children: [_jsx("label", { className: "label", children: "Add product" }), _jsxs("select", { className: "input", value: productId, onChange: (e) => setProductId(e.target.value), children: [_jsx("option", { value: "", children: "\u2014 Select \u2014" }), products.data?.results.map((p) => (_jsx("option", { value: p.id, children: p.name }, p.id)))] })] }), _jsxs("div", { className: "col-span-4", children: [_jsx("label", { className: "label", children: "Qty per unit" }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: qty, onChange: (e) => setQty(e.target.value) })] }), _jsx("button", { className: "col-span-1 btn-primary px-2 py-2", disabled: !productId || !qty || add.isPending, onClick: () => add.mutate(), "aria-label": "Add", children: _jsx(Plus, { size: 16 }) })] })] }));
}
// ── Adjust stock ──────────────────────────────────────────────────────────
function AdjustModal({ material, onClose }) {
    const qc = useQueryClient();
    const [delta, setDelta] = useState('');
    const [note, setNote] = useState('');
    const mutate = useMutation({
        mutationFn: () => processedMaterials.stock.adjust({
            processed_material: material.id,
            quantity_delta: Number(delta),
            note,
        }),
        onSuccess: () => {
            toast.success('Adjustment recorded.');
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
            qc.invalidateQueries({ queryKey: ['processed-movements'] });
            onClose();
            setDelta('');
            setNote('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!material)
        return null;
    return (_jsxs(Modal, { open: !!material, onClose: onClose, title: `Adjust: ${material.name}`, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !delta || Number(delta) === 0 || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending ? 'Saving…' : 'Apply' })] }), children: [_jsxs("p", { className: "text-sm text-slate-500 mb-3", children: ["Current on-hand: ", _jsxs("strong", { children: [formatNumber(material.stock_quantity, 2), " ", material.unit] }), ". Positive to add, negative to remove (e.g. waste)."] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsxs("label", { className: "label", children: ["Delta (", material.unit, ")"] }), _jsx("input", { autoFocus: true, type: "number", step: "0.01", className: "input", value: delta, onChange: (e) => setDelta(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Note (optional)" }), _jsx("textarea", { className: "input", rows: 2, value: note, onChange: (e) => setNote(e.target.value) })] })] })] }));
}
// ── Produce a batch ───────────────────────────────────────────────────────
function ProduceModal({ material, onClose }) {
    const qc = useQueryClient();
    const [batches, setBatches] = useState('1');
    const [scheduledFor, setScheduledFor] = useState(new Date().toISOString().slice(0, 10));
    const [notes, setNotes] = useState('');
    const produce = useMutation({
        mutationFn: () => processedMaterials.batches.produce({
            processed_material: material.id,
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
            onClose();
            setBatches('1');
            setNotes('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!material)
        return null;
    const yieldPerBatch = Number(material.yield_per_batch);
    const projected = (Number(batches) || 0) * yieldPerBatch;
    return (_jsxs(Modal, { open: !!material, onClose: onClose, title: `Produce batch — ${material.name}`, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !batches || Number(batches) <= 0 || produce.isPending, onClick: () => produce.mutate(), children: produce.isPending ? 'Producing…' : 'Produce' })] }), children: [_jsxs("p", { className: "text-sm text-slate-500 mb-3", children: ["Each batch yields ", _jsxs("strong", { children: [formatNumber(material.yield_per_batch), " ", material.unit] }), ". Will produce ", _jsxs("strong", { children: [formatNumber(projected, 0), " ", material.unit] }), " and consume raw materials per recipe."] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "Batches" }), _jsx("input", { autoFocus: true, type: "number", step: "0.01", min: "0.01", className: "input", value: batches, onChange: (e) => setBatches(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Scheduled for" }), _jsx("input", { type: "date", className: "input", value: scheduledFor, onChange: (e) => setScheduledFor(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Notes" }), _jsx("textarea", { className: "input", rows: 2, value: notes, onChange: (e) => setNotes(e.target.value) })] })] })] }));
}
// ── Batches tab ───────────────────────────────────────────────────────────
function BatchesTab() {
    const list = useCrudList({
        queryKey: ['processed-batches'],
        fetcher: (p) => processedMaterials.batches.list(p),
        deleter: (id) => processedMaterials.batches.remove(id),
    });
    const columns = [
        { key: 'sched', header: 'Scheduled', render: (r) => formatDate(r.scheduled_for) },
        { key: 'material', header: 'Material', render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.processed_material_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.processed_material_sku })] })) },
        { key: 'batches', header: 'Batches', align: 'right', render: (r) => formatNumber(r.batches, 2) },
        { key: 'qty', header: 'Produced', align: 'right', render: (r) => (`${formatNumber(r.quantity_produced, 1)} ${r.processed_material_unit}`) },
        { key: 'cost', header: 'Cost', align: 'right', render: (r) => formatMoney(r.cost) },
        { key: 'when', header: 'Completed', render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
        { key: 'by', header: 'By', render: (r) => r.created_by_name ?? '—' },
    ];
    const exportColumns = [
        { key: 'scheduled_for', header: 'Scheduled', value: (r) => r.scheduled_for },
        { key: 'completed_at', header: 'Completed', value: (r) => r.completed_at ?? '' },
        { key: 'processed_material_sku', header: 'Material SKU', value: (r) => r.processed_material_sku },
        { key: 'processed_material_name', header: 'Material', value: (r) => r.processed_material_name },
        { key: 'batches', header: 'Batches', value: (r) => Number(r.batches) },
        { key: 'quantity_produced', header: 'Produced', value: (r) => Number(r.quantity_produced) },
        { key: 'processed_material_unit', header: 'Unit', value: (r) => r.processed_material_unit },
        { key: 'cost', header: 'Cost', value: (r) => Number(r.cost) },
        { key: 'created_by', header: 'By', value: (r) => r.created_by_name ?? '' },
        { key: 'notes', header: 'Notes', value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search batches\u2026" }), _jsx(ExportMenu, { filename: "processed-batches", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => processedMaterials.batches.list(p), list.search ? { search: list.search } : {}) })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: PlayCircle, title: "No batches recorded", description: "Use the \u25B6 button on a material to record one." }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }));
}
// ── Movements tab ─────────────────────────────────────────────────────────
function MovementsTab() {
    const list = useCrudList({
        queryKey: ['processed-movements'],
        fetcher: (p) => processedMaterials.movements.list(p),
    });
    const columns = [
        { key: 'when', header: 'When', render: (r) => formatDateTime(r.created_at) },
        { key: 'item', header: 'Material', render: (r) => _jsx("span", { className: "font-medium", children: r.item_name }) },
        { key: 'reason', header: 'Reason', render: (r) => _jsx("span", { className: "badge-gray", children: r.reason_display }) },
        { key: 'delta', header: 'Δ', align: 'right', render: (r) => (_jsxs("span", { className: Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold', children: [Number(r.quantity_delta) > 0 ? '+' : '', formatNumber(r.quantity_delta, 2), " ", r.item_unit] })) },
        { key: 'balance', header: 'After', align: 'right', render: (r) => (`${formatNumber(r.balance_after, 2)} ${r.item_unit}`) },
        { key: 'ref', header: 'Ref', render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.reference || '—' }) },
        { key: 'who', header: 'By', render: (r) => r.created_by_name ?? '—' },
    ];
    const exportColumns = [
        { key: 'created_at', header: 'When', value: (r) => r.created_at },
        { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
        { key: 'item_name', header: 'Material', value: (r) => r.item_name },
        { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
        { key: 'reason', header: 'Reason', value: (r) => r.reason_display },
        { key: 'quantity_delta', header: 'Quantity delta', value: (r) => Number(r.quantity_delta) },
        { key: 'balance_after', header: 'Balance after', value: (r) => Number(r.balance_after) },
        { key: 'reference', header: 'Reference', value: (r) => r.reference },
        { key: 'note', header: 'Note', value: (r) => r.note },
        { key: 'created_by', header: 'By', value: (r) => r.created_by_name ?? '' },
    ];
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "px-5 pt-3 flex items-center justify-end", children: _jsx(ExportMenu, { filename: "processed-movements", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => processedMaterials.movements.list(p)) }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: History, title: "No movements yet" }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }));
}
