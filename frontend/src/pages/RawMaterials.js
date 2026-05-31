import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Tag, PackagePlus } from 'lucide-react';
import { toast } from 'sonner';
import { catalog, inventory } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
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
    sku: '', name: '', unit: 'g', unit_cost: '0', reorder_threshold: '0',
    preferred_supplier: null, is_active: true,
};
export function RawMaterialsPage() {
    const qc = useQueryClient();
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
    const save = useMutation({
        mutationFn: () => editing ? catalog.rawMaterials.update(editing.id, form) : catalog.rawMaterials.create(form),
        onSuccess: () => {
            toast.success(editing ? 'Material updated.' : 'Material created.');
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
            toast.success(`Received ${receiveQty} ${receiveOpen?.unit}.`);
            qc.invalidateQueries({ queryKey: ['stock'] });
            setReceiveOpen(null);
            setReceiveQty('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
    function openEdit(row) { setEditing(row); setForm(row); setOpen(true); }
    const columns = [
        { key: 'sku', header: 'SKU', render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.sku }) },
        { key: 'name', header: 'Name', render: (r) => _jsx("span", { className: "font-medium", children: r.name }) },
        { key: 'unit', header: 'Unit', render: (r) => r.unit },
        { key: 'cost', header: 'Cost / unit', align: 'right', render: (r) => formatMoney(r.unit_cost) },
        { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
        { key: 'supplier', header: 'Supplier', render: (r) => r.preferred_supplier_name ?? '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5 text-emerald-700", title: "Receive stock", onClick: (e) => { e.stopPropagation(); setReceiveOpen(r); }, children: _jsx(PackagePlus, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })) },
    ];
    const exportColumns = [
        { key: 'sku', header: 'SKU', value: (r) => r.sku },
        { key: 'name', header: 'Name', value: (r) => r.name },
        { key: 'unit', header: 'Unit', value: (r) => r.unit },
        { key: 'unit_cost', header: 'Unit cost', value: (r) => Number(r.unit_cost) },
        { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
        { key: 'preferred_supplier', header: 'Preferred supplier', value: (r) => r.preferred_supplier_name ?? '' },
        { key: 'is_active', header: 'Active', value: (r) => (r.is_active ? 'yes' : 'no') },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Raw materials", subtitle: "Ingredients & supplies consumed by production", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "raw-materials", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => catalog.rawMaterials.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " New material"] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search by name or SKU\u2026" }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Tag, title: "No raw materials yet", description: "Add ingredients used in production." }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? 'Edit raw material' : 'New raw material', size: "lg", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", onClick: () => save.mutate(), disabled: save.isPending || !form.name || !form.sku, children: save.isPending ? 'Saving…' : 'Save' })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "SKU" }), _jsx("input", { className: "input font-mono", value: form.sku ?? '', onChange: (e) => setForm({ ...form, sku: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Name" }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Unit" }), _jsx("select", { className: "input", value: form.unit ?? 'g', onChange: (e) => setForm({ ...form, unit: e.target.value }), children: units.data?.map((u) => _jsx("option", { value: u.value, children: u.label }, u.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Cost per unit" }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: form.unit_cost ?? '0', onChange: (e) => setForm({ ...form, unit_cost: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Reorder threshold" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.reorder_threshold ?? '0', onChange: (e) => setForm({ ...form, reorder_threshold: e.target.value }) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Preferred supplier" }), _jsxs("select", { className: "input", value: form.preferred_supplier ?? '', onChange: (e) => setForm({ ...form, preferred_supplier: e.target.value || null }), children: [_jsx("option", { value: "", children: "\u2014 None \u2014" }), suppliers.data?.results.map((s) => _jsx("option", { value: s.id, children: s.name }, s.id))] })] }), _jsxs("div", { className: "sm:col-span-2 flex items-center gap-2", children: [_jsx("input", { id: "active-rm", type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), _jsx("label", { htmlFor: "active-rm", className: "text-sm", children: "Active" })] })] }) }), _jsx(Modal, { open: !!receiveOpen, onClose: () => setReceiveOpen(null), title: `Receive: ${receiveOpen?.name ?? ''}`, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setReceiveOpen(null), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !receiveQty || Number(receiveQty) <= 0 || receive.isPending, onClick: () => receive.mutate(), children: receive.isPending ? 'Recording…' : 'Record' })] }), children: _jsxs("div", { children: [_jsxs("label", { className: "label", children: ["Quantity received (", receiveOpen?.unit, ")"] }), _jsx("input", { autoFocus: true, type: "number", step: "0.01", className: "input", value: receiveQty, onChange: (e) => setReceiveQty(e.target.value) }), _jsx("p", { className: "text-xs text-slate-500 mt-2", children: "This logs a stock-in movement and updates current on-hand stock." })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete material?", message: `Delete "${toDelete?.name}"? Linked recipes will also be affected.`, confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
