import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Boxes, AlertTriangle, History, Sliders, ChefHat } from 'lucide-react';
import { toast } from 'sonner';
import { inventory } from '@/api/endpoints';
import { processedMaterials } from '@/api/processed-materials';
import { extractErrorMessage } from '@/api/client';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { useCrudList } from '@/hooks/useCrudList';
import { formatNumber, formatDateTime } from '@/lib/format';
export function InventoryPage() {
    const [tab, setTab] = useState('all');
    const [adjustOpen, setAdjustOpen] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Inventory", subtitle: "On-hand stock for products, raw materials, and processed materials" }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header gap-2 flex-wrap", children: _jsx("div", { className: "flex gap-1", children: [
                                { key: 'all', label: 'All stock', icon: Boxes },
                                { key: 'low', label: 'Low stock', icon: AlertTriangle },
                                { key: 'processed', label: 'Processed', icon: ChefHat },
                                { key: 'movements', label: 'Movements', icon: History },
                            ].map(({ key, label, icon: Icon }) => (_jsxs("button", { onClick: () => setTab(key), className: `px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: [_jsx(Icon, { size: 14 }), " ", label] }, key))) }) }), tab === 'all' && _jsx(AllStockTab, { onAdjust: setAdjustOpen }), tab === 'low' && _jsx(LowStockTab, { onAdjust: setAdjustOpen }), tab === 'processed' && _jsx(ProcessedStockTab, {}), tab === 'movements' && _jsx(MovementsTab, {})] }), _jsx(AdjustModal, { stock: adjustOpen, onClose: () => setAdjustOpen(null) })] }));
}
// ── Tabs ──────────────────────────────────────────────────────────────────
function StockColumns(onAdjust) {
    return [
        { key: 'name', header: 'Item', render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.item_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.item_sku })] })) },
        { key: 'kind', header: 'Type', render: (r) => r.kind === 'product' ? _jsx("span", { className: "badge-blue", children: "Product" }) : _jsx("span", { className: "badge-gray", children: "Material" })
        },
        { key: 'qty', header: 'On hand', align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatNumber(r.quantity, 2), " ", r.item_unit] })) },
        { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
        { key: 'status', header: 'Status', render: (r) => r.is_low ? _jsx("span", { className: "badge-red", children: "Low" }) : _jsx("span", { className: "badge-green", children: "OK" })
        },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("button", { className: "btn-secondary px-2 py-1 text-xs", onClick: () => onAdjust(r), children: [_jsx(Sliders, { size: 12 }), " Adjust"] })) },
    ];
}
const stockExportColumns = [
    { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
    { key: 'item_name', header: 'Item', value: (r) => r.item_name },
    { key: 'kind', header: 'Type', value: (r) => r.kind },
    { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
    { key: 'quantity', header: 'On hand', value: (r) => Number(r.quantity) },
    { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
    { key: 'is_low', header: 'Low stock', value: (r) => (r.is_low ? 'yes' : 'no') },
];
function AllStockTab({ onAdjust }) {
    const list = useCrudList({
        queryKey: ['stock'],
        fetcher: (p) => inventory.stock.list(p),
    });
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search stock items\u2026" }), _jsx(ExportMenu, { filename: "stock", columns: stockExportColumns, fetchRows: () => fetchAllPaginated((p) => inventory.stock.list(p), list.search ? { search: list.search } : {}) })] }), _jsx(DataTable, { columns: StockColumns(onAdjust), data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Boxes, title: "No stock yet", description: "Stock entries appear as you create products and materials." }) }), list.data && _jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })] }));
}
function LowStockTab({ onAdjust }) {
    const { data, isLoading } = useQuery({
        queryKey: ['stock-low'],
        queryFn: () => inventory.stock.low(),
    });
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "px-5 pt-3 flex items-center justify-end", children: _jsx(ExportMenu, { filename: "low-stock", columns: stockExportColumns, fetchRows: async () => (await inventory.stock.low()).results }) }), _jsx(DataTable, { columns: StockColumns(onAdjust), data: data?.results, loading: isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: AlertTriangle, title: "No items below threshold", description: "All stocks look healthy." }) })] }));
}
function MovementsTab() {
    const list = useCrudList({
        queryKey: ['movements'],
        fetcher: (p) => inventory.movements.list(p),
    });
    const columns = [
        { key: 'when', header: 'When', render: (r) => formatDateTime(r.created_at) },
        { key: 'item', header: 'Item', render: (r) => _jsx("span", { className: "font-medium", children: r.item_name }) },
        { key: 'reason', header: 'Reason', render: (r) => _jsx("span", { className: "badge-gray", children: r.reason_display }) },
        { key: 'delta', header: 'Δ', align: 'right', render: (r) => (_jsxs("span", { className: Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold', children: [Number(r.quantity_delta) > 0 ? '+' : '', formatNumber(r.quantity_delta, 2), " ", r.item_unit] })) },
        { key: 'balance', header: 'After', align: 'right', render: (r) => `${formatNumber(r.balance_after, 2)} ${r.item_unit}` },
        { key: 'ref', header: 'Ref', render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.reference || '—' }) },
        { key: 'who', header: 'By', render: (r) => r.created_by_name ?? '—' },
    ];
    const exportColumns = [
        { key: 'created_at', header: 'When', value: (r) => r.created_at },
        { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
        { key: 'item_name', header: 'Item', value: (r) => r.item_name },
        { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
        { key: 'reason', header: 'Reason', value: (r) => r.reason_display },
        { key: 'quantity_delta', header: 'Quantity delta', value: (r) => Number(r.quantity_delta) },
        { key: 'balance_after', header: 'Balance after', value: (r) => Number(r.balance_after) },
        { key: 'reference', header: 'Reference', value: (r) => r.reference },
        { key: 'note', header: 'Note', value: (r) => r.note },
        { key: 'created_by', header: 'By', value: (r) => r.created_by_name ?? '' },
    ];
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "px-5 pt-3 flex items-center justify-end", children: _jsx(ExportMenu, { filename: "stock-movements", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => inventory.movements.list(p)) }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: History, title: "No stock movements yet" }) }), list.data && _jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })] }));
}
function AdjustModal({ stock, onClose }) {
    const qc = useQueryClient();
    const [delta, setDelta] = useState('');
    const [note, setNote] = useState('');
    const mutate = useMutation({
        mutationFn: () => inventory.stock.adjust({
            product: stock?.kind === 'product' ? stock.product : undefined,
            raw_material: stock?.kind === 'raw_material' ? stock.raw_material : undefined,
            quantity_delta: Number(delta),
            note,
        }),
        onSuccess: () => {
            toast.success('Adjustment recorded.');
            qc.invalidateQueries({ queryKey: ['stock'] });
            qc.invalidateQueries({ queryKey: ['movements'] });
            qc.invalidateQueries({ queryKey: ['stock-low'] });
            onClose();
            setDelta('');
            setNote('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!stock)
        return null;
    return (_jsxs(Modal, { open: !!stock, onClose: onClose, title: `Adjust: ${stock.item_name}`, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !delta || Number(delta) === 0 || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending ? 'Saving…' : 'Apply' })] }), children: [_jsxs("p", { className: "text-sm text-slate-500 mb-3", children: ["Current on-hand: ", _jsxs("strong", { children: [formatNumber(stock.quantity, 2), " ", stock.item_unit] }), ". Enter a positive number to add stock, negative to remove (e.g. waste)."] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsxs("label", { className: "label", children: ["Delta (", stock.item_unit, ")"] }), _jsx("input", { type: "number", step: "0.01", className: "input", value: delta, onChange: (e) => setDelta(e.target.value), autoFocus: true })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Note (optional)" }), _jsx("textarea", { className: "input", rows: 2, value: note, onChange: (e) => setNote(e.target.value) })] })] })] }));
}
// ── Processed materials stock tab ─────────────────────────────────────────
function ProcessedStockTab() {
    const list = useCrudList({
        queryKey: ['processed-stock'],
        fetcher: (p) => processedMaterials.stock.list(p),
    });
    const columns = [
        { key: 'name', header: 'Item', render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.item_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.item_sku })] })) },
        { key: 'kind', header: 'Type', render: () => (_jsx("span", { className: "badge-yellow", children: "Processed" })) },
        { key: 'qty', header: 'On hand', align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatNumber(r.quantity, 2), " ", r.item_unit] })) },
        { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => (formatNumber(r.reorder_threshold, 2)) },
        { key: 'status', header: 'Status', render: (r) => (r.is_low ? _jsx("span", { className: "badge-red", children: "Low" }) : _jsx("span", { className: "badge-green", children: "OK" })) },
    ];
    const exportColumns = [
        { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
        { key: 'item_name', header: 'Item', value: (r) => r.item_name },
        { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
        { key: 'quantity', header: 'On hand', value: (r) => Number(r.quantity) },
        { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
        { key: 'is_low', header: 'Low stock', value: (r) => (r.is_low ? 'yes' : 'no') },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search processed materials\u2026" }), _jsx(ExportMenu, { filename: "processed-stock", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => processedMaterials.stock.list(p), list.search ? { search: list.search } : {}) })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: ChefHat, title: "No processed materials in stock", description: 'Manage processed materials under Catalog \u2192 Processed materials.' }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }));
}
