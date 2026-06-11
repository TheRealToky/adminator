import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatMoney, formatQuantity } from '@/lib/format';
const empty = {
    sku: '', name: '', unit: 'g', unit_cost: '0', reorder_threshold: '0',
    preferred_supplier: null, is_active: true,
};
export function RawMaterialsPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['raw-materials'],
        fetcher: (p) => catalog.rawMaterials.list(p),
        deleter: (id) => catalog.rawMaterials.remove(id),
    });
    const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
    const suppliers = useQuery({ queryKey: ['suppliers-all'], queryFn: () => catalog.suppliers.list({ page_size: 200 }) });
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(empty);
    const [toDelete, setToDelete] = useState(null);
    const [receiveOpen, setReceiveOpen] = useState(null);
    const [receiveQty, setReceiveQty] = useState('');
    const [usageFor, setUsageFor] = useState(null);
    const save = useMutation({
        mutationFn: () => editing ? catalog.rawMaterials.update(editing.id, form) : catalog.rawMaterials.create(form),
        onSuccess: () => {
            toast.success(editing ? t('rawMaterials.updated') : t('rawMaterials.created'));
            qc.invalidateQueries({ queryKey: ['raw-materials'] });
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const receive = useMutation({
        mutationFn: () => inventory.stock.receive({
            raw_material: receiveOpen.id,
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
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'sku', header: t('rawMaterials.columns.sku'), render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.sku }) },
        { key: 'name', header: t('rawMaterials.columns.name'), render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'unit', header: t('rawMaterials.columns.unit'), render: (r) => r.unit },
        { key: 'cost', header: t('rawMaterials.columns.cost'), align: 'right', render: (r) => formatMoney(r.unit_cost) },
        { key: 'thresh', header: t('rawMaterials.columns.reorder'), align: 'right', render: (r) => formatQuantity(r.reorder_threshold) },
        { key: 'supplier', header: t('rawMaterials.columns.supplier'), render: (r) => r.preferred_supplier_name ?? '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5 text-emerald-700", title: t('rawMaterials.receive.receiveStock'), onClick: (e) => { e.stopPropagation(); setReceiveOpen(r); }, children: _jsx(PackagePlus, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-blue-700", title: t('rawMaterials.actions.usedIn'), onClick: (e) => { e.stopPropagation(); setUsageFor(r); }, children: _jsx(ChefHat, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'sku', header: t('rawMaterials.exportCols.sku'), value: (r) => r.sku },
        { key: 'name', header: t('rawMaterials.exportCols.name'), value: (r) => r.name },
        { key: 'unit', header: t('rawMaterials.exportCols.unit'), value: (r) => r.unit },
        { key: 'unit_cost', header: t('rawMaterials.exportCols.unitCost'), value: (r) => Number(r.unit_cost) },
        { key: 'reorder_threshold', header: t('rawMaterials.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'preferred_supplier', header: t('rawMaterials.exportCols.preferredSupplier'), value: (r) => r.preferred_supplier_name ?? '' },
        { key: 'is_active', header: t('rawMaterials.exportCols.active'), value: (r) => (r.is_active ? t('common.yes') : t('common.no')) },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('rawMaterials.title'), subtitle: t('rawMaterials.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "raw-materials", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => catalog.rawMaterials.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('rawMaterials.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('rawMaterials.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Tag, title: t('rawMaterials.emptyTitle'), description: t('rawMaterials.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('rawMaterials.edit') : t('rawMaterials.newTitle'), size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", onClick: () => save.mutate(), disabled: save.isPending || !form.name || !form.sku, children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.sku') }), _jsx("input", { className: "input font-mono", value: form.sku ?? '', onChange: (e) => setForm({ ...form, sku: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.unit') }), _jsx("select", { className: "input", value: form.unit ?? 'g', onChange: (e) => setForm({ ...form, unit: e.target.value }), children: units.data?.map((u) => _jsx("option", { value: u.value, children: u.label }, u.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.costPerUnit') }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: form.unit_cost ?? '0', onChange: (e) => setForm({ ...form, unit_cost: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.reorderThreshold') }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: form.reorder_threshold ?? '0', onChange: (e) => setForm({ ...form, reorder_threshold: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.fields.preferredSupplier') }), _jsxs("select", { className: "input", value: form.preferred_supplier ?? '', onChange: (e) => setForm({ ...form, preferred_supplier: e.target.value || null }), children: [_jsx("option", { value: "", children: t('common.none') }), suppliers.data?.results.map((s) => _jsx("option", { value: s.id, children: s.name }, s.id))] })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-rm", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-rm", className: "text-sm", children: t('rawMaterials.fields.active') })] })] }) }), _jsx(Modal, { open: !!receiveOpen, onClose: () => setReceiveOpen(null), title: t('rawMaterials.receive.title', { name: receiveOpen?.name ?? '' }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setReceiveOpen(null), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !receiveQty || Number(receiveQty) <= 0 || receive.isPending, onClick: () => receive.mutate(), children: receive.isPending ? t('rawMaterials.receive.recording') : t('rawMaterials.receive.record') })] }), children: _jsxs("div", { children: [_jsx("label", { className: "label", children: t('rawMaterials.receive.qtyLabel', { unit: receiveOpen?.unit ?? '' }) }), _jsx("input", { autoFocus: true, type: "number", step: "0.0001", className: "input", value: receiveQty, onChange: (e) => setReceiveQty(e.target.value) }), _jsx("p", { className: "text-xs text-slate-500 mt-2", children: t('rawMaterials.receive.hint') })] }) }), _jsx(UsageModal, { material: usageFor, onClose: () => setUsageFor(null) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('rawMaterials.deleteTitle'), message: t('rawMaterials.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
// ── Usage modal (products & processed materials using this raw material) ──
function UsageModal({ material: materialProp, onClose, }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
    // Read live material data so the list updates as we remove items, without
    // depending on the parent list query to refresh.
    const materialQuery = useQuery({
        queryKey: ['raw-material', materialProp?.id],
        queryFn: () => catalog.rawMaterials.get(materialProp.id),
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
        mutationFn: (id) => catalog.recipes.remove(id),
        onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const removeProcessedRecipeItem = useMutation({
        mutationFn: (id) => processedMaterialsApi.recipes.remove(id),
        onSuccess: () => { toast.success(t('common.removed')); invalidateAll(); },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const products = material?.used_in_products ?? [];
    const processed = material?.used_in_processed_materials ?? [];
    const hasAny = products.length > 0 || processed.length > 0;
    return (_jsxs(Modal, { open: !!materialProp, onClose: onClose, title: t('rawMaterials.usage.title', { name: material?.name ?? '' }), size: "lg", children: [_jsx("p", { className: "text-sm text-slate-500 mb-4", children: _jsx(Trans, { i18nKey: "rawMaterials.usage.lead", components: { 1: _jsx("strong", {}) } }) }), !hasAny && (_jsx("p", { className: "px-3 py-6 text-center text-sm text-slate-400 border border-slate-200 rounded-md", children: t('rawMaterials.usage.empty') })), products.length > 0 && (_jsxs("section", { className: "mb-4", children: [_jsx("h4", { className: "text-xs uppercase tracking-wider text-slate-500 mb-2 px-1", children: t('rawMaterials.usage.productsHeader') }), _jsx("ul", { className: "divide-y divide-slate-100 border border-slate-200 rounded-md", children: products.map((it) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsxs("span", { className: "col-span-7 text-sm flex items-center gap-2", children: [_jsx("span", { className: "badge-gray", children: t('rawMaterials.usage.badgeProduct') }), _jsx("span", { className: "font-medium", children: it.product_name }), _jsx("span", { className: "text-xs text-slate-500 font-mono", children: it.product_sku })] }), _jsxs("span", { className: "col-span-4 text-right text-sm", children: [formatQuantity(it.quantity), " ", material?.unit] }), _jsx("button", { className: "col-span-1 text-red-500 hover:text-red-700 justify-self-end", title: t('common.removed'), disabled: removeRecipeItem.isPending, onClick: () => removeRecipeItem.mutate(it.id), children: _jsx(X, { size: 16 }) })] }, it.id))) })] })), processed.length > 0 && (_jsxs("section", { children: [_jsx("h4", { className: "text-xs uppercase tracking-wider text-slate-500 mb-2 px-1", children: t('rawMaterials.usage.processedHeader') }), _jsx("ul", { className: "divide-y divide-slate-100 border border-slate-200 rounded-md", children: processed.map((it) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsxs("span", { className: "col-span-7 text-sm flex items-center gap-2", children: [_jsx("span", { className: "badge-blue", children: t('rawMaterials.usage.badgeProcessed') }), _jsx("span", { className: "font-medium", children: it.processed_material_name }), _jsx("span", { className: "text-xs text-slate-500 font-mono", children: it.processed_material_sku })] }), _jsxs("span", { className: "col-span-4 text-right text-sm", children: [formatQuantity(it.quantity), " ", material?.unit] }), _jsx("button", { className: "col-span-1 text-red-500 hover:text-red-700 justify-self-end", title: t('common.removed'), disabled: removeProcessedRecipeItem.isPending, onClick: () => removeProcessedRecipeItem.mutate(it.id), children: _jsx(X, { size: 16 }) })] }, it.id))) })] })), _jsx("p", { className: "text-xs text-slate-500 mt-4", children: t('rawMaterials.usage.hint') })] }));
}
