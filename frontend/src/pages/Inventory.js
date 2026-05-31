import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Boxes, AlertTriangle, History, Sliders, ChefHat } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
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
    const { t } = useTranslation();
    const [tab, setTab] = useState('all');
    const [adjustOpen, setAdjustOpen] = useState(null);
    const tabs = [
        { key: 'all', label: t('inventory.tabs.all'), icon: Boxes },
        { key: 'low', label: t('inventory.tabs.low'), icon: AlertTriangle },
        { key: 'processed', label: t('inventory.tabs.processed'), icon: ChefHat },
        { key: 'movements', label: t('inventory.tabs.movements'), icon: History },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('inventory.title'), subtitle: t('inventory.subtitle') }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header gap-2 flex-wrap", children: _jsx("div", { className: "flex gap-1", children: tabs.map(({ key, label, icon: Icon }) => (_jsxs("button", { onClick: () => setTab(key), className: `px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: [_jsx(Icon, { size: 14 }), " ", label] }, key))) }) }), tab === 'all' && _jsx(AllStockTab, { onAdjust: setAdjustOpen }), tab === 'low' && _jsx(LowStockTab, { onAdjust: setAdjustOpen }), tab === 'processed' && _jsx(ProcessedStockTab, {}), tab === 'movements' && _jsx(MovementsTab, {})] }), _jsx(AdjustModal, { stock: adjustOpen, onClose: () => setAdjustOpen(null) })] }));
}
// ── Tabs ──────────────────────────────────────────────────────────────────
function useStockColumns(onAdjust) {
    const { t } = useTranslation();
    return [
        { key: 'name', header: t('inventory.columns.item'), render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.item_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.item_sku })] })) },
        { key: 'kind', header: t('inventory.columns.type'), render: (r) => r.kind === 'product'
                ? _jsx("span", { className: "badge-blue", children: t('inventory.badges.product') })
                : _jsx("span", { className: "badge-gray", children: t('inventory.badges.material') })
        },
        { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatNumber(r.quantity, 2), " ", r.item_unit] })) },
        { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
        { key: 'status', header: t('inventory.columns.status'), render: (r) => r.is_low
                ? _jsx("span", { className: "badge-red", children: t('inventory.badges.low') })
                : _jsx("span", { className: "badge-green", children: t('inventory.badges.ok') })
        },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("button", { className: "btn-secondary px-2 py-1 text-xs", onClick: () => onAdjust(r), children: [_jsx(Sliders, { size: 12 }), " ", t('inventory.actions.adjust')] })) },
    ];
}
function useStockExportColumns() {
    const { t } = useTranslation();
    return [
        { key: 'item_sku', header: t('inventory.exportCols.sku'), value: (r) => r.item_sku },
        { key: 'item_name', header: t('inventory.exportCols.item'), value: (r) => r.item_name },
        { key: 'kind', header: t('inventory.exportCols.type'), value: (r) => r.kind },
        { key: 'item_unit', header: t('inventory.exportCols.unit'), value: (r) => r.item_unit },
        { key: 'quantity', header: t('inventory.exportCols.onHand'), value: (r) => Number(r.quantity) },
        { key: 'reorder_threshold', header: t('inventory.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'is_low', header: t('inventory.exportCols.lowStock'), value: (r) => (r.is_low ? t('common.yes') : t('common.no')) },
    ];
}
function AllStockTab({ onAdjust }) {
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['stock'],
        fetcher: (p) => inventory.stock.list(p),
    });
    const columns = useStockColumns(onAdjust);
    const exportColumns = useStockExportColumns();
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('inventory.search.all') }), _jsx(ExportMenu, { filename: "stock", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => inventory.stock.list(p), list.search ? { search: list.search } : {}) })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Boxes, title: t('inventory.empty.stock'), description: t('inventory.empty.stockDescription') }) }), list.data && _jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })] }));
}
function LowStockTab({ onAdjust }) {
    const { t } = useTranslation();
    const { data, isLoading } = useQuery({
        queryKey: ['stock-low'],
        queryFn: () => inventory.stock.low(),
    });
    const columns = useStockColumns(onAdjust);
    const exportColumns = useStockExportColumns();
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "px-5 pt-3 flex items-center justify-end", children: _jsx(ExportMenu, { filename: "low-stock", columns: exportColumns, fetchRows: async () => (await inventory.stock.low()).results }) }), _jsx(DataTable, { columns: columns, data: data?.results, loading: isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: AlertTriangle, title: t('inventory.empty.low'), description: t('inventory.empty.lowDescription') }) })] }));
}
function MovementsTab() {
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['movements'],
        fetcher: (p) => inventory.movements.list(p),
    });
    const columns = [
        { key: 'when', header: t('inventory.columns.when'), render: (r) => formatDateTime(r.created_at) },
        { key: 'item', header: t('inventory.columns.item'), render: (r) => _jsx("span", { className: "font-medium", children: r.item_name }) },
        { key: 'reason', header: t('inventory.columns.reason'), render: (r) => _jsx("span", { className: "badge-gray", children: r.reason_display }) },
        { key: 'delta', header: t('inventory.columns.delta'), align: 'right', render: (r) => (_jsxs("span", { className: Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold', children: [Number(r.quantity_delta) > 0 ? '+' : '', formatNumber(r.quantity_delta, 2), " ", r.item_unit] })) },
        { key: 'balance', header: t('inventory.columns.after'), align: 'right', render: (r) => `${formatNumber(r.balance_after, 2)} ${r.item_unit}` },
        { key: 'ref', header: t('inventory.columns.ref'), render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.reference || '—' }) },
        { key: 'who', header: t('inventory.columns.by'), render: (r) => r.created_by_name ?? '—' },
    ];
    const exportColumns = [
        { key: 'created_at', header: t('inventory.exportCols.when'), value: (r) => r.created_at },
        { key: 'item_sku', header: t('inventory.exportCols.sku'), value: (r) => r.item_sku },
        { key: 'item_name', header: t('inventory.exportCols.item'), value: (r) => r.item_name },
        { key: 'item_unit', header: t('inventory.exportCols.unit'), value: (r) => r.item_unit },
        { key: 'reason', header: t('inventory.exportCols.reason'), value: (r) => r.reason_display },
        { key: 'quantity_delta', header: t('inventory.exportCols.quantityDelta'), value: (r) => Number(r.quantity_delta) },
        { key: 'balance_after', header: t('inventory.exportCols.balanceAfter'), value: (r) => Number(r.balance_after) },
        { key: 'reference', header: t('inventory.exportCols.reference'), value: (r) => r.reference },
        { key: 'note', header: t('inventory.exportCols.note'), value: (r) => r.note },
        { key: 'created_by', header: t('inventory.exportCols.by'), value: (r) => r.created_by_name ?? '' },
    ];
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "px-5 pt-3 flex items-center justify-end", children: _jsx(ExportMenu, { filename: "stock-movements", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => inventory.movements.list(p)) }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: History, title: t('inventory.empty.movements') }) }), list.data && _jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })] }));
}
function AdjustModal({ stock, onClose }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
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
            toast.success(t('inventory.adjust.recorded'));
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
    return (_jsxs(Modal, { open: !!stock, onClose: onClose, title: t('inventory.adjust.title', { name: stock.item_name }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !delta || Number(delta) === 0 || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending ? t('common.saving') : t('common.apply') })] }), children: [_jsx("p", { className: "text-sm text-slate-500 mb-3", dangerouslySetInnerHTML: {
                    __html: t('inventory.adjust.currentOnHand', {
                        qty: formatNumber(stock.quantity, 2),
                        unit: stock.item_unit,
                    }),
                } }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('inventory.adjust.delta', { unit: stock.item_unit }) }), _jsx("input", { type: "number", step: "0.01", className: "input", value: delta, onChange: (e) => setDelta(e.target.value), autoFocus: true })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('common.noteOptional') }), _jsx("textarea", { className: "input", rows: 2, value: note, onChange: (e) => setNote(e.target.value) })] })] })] }));
}
// ── Processed materials stock tab ─────────────────────────────────────────
function ProcessedStockTab() {
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['processed-stock'],
        fetcher: (p) => processedMaterials.stock.list(p),
    });
    const columns = [
        { key: 'name', header: t('inventory.columns.item'), render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.item_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.item_sku })] })) },
        { key: 'kind', header: t('inventory.columns.type'), render: () => (_jsx("span", { className: "badge-yellow", children: t('inventory.badges.processed') })) },
        { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatNumber(r.quantity, 2), " ", r.item_unit] })) },
        { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => (formatNumber(r.reorder_threshold, 2)) },
        { key: 'status', header: t('inventory.columns.status'), render: (r) => (r.is_low
                ? _jsx("span", { className: "badge-red", children: t('inventory.badges.low') })
                : _jsx("span", { className: "badge-green", children: t('inventory.badges.ok') })) },
    ];
    const exportColumns = [
        { key: 'item_sku', header: t('inventory.exportCols.sku'), value: (r) => r.item_sku },
        { key: 'item_name', header: t('inventory.exportCols.item'), value: (r) => r.item_name },
        { key: 'item_unit', header: t('inventory.exportCols.unit'), value: (r) => r.item_unit },
        { key: 'quantity', header: t('inventory.exportCols.onHand'), value: (r) => Number(r.quantity) },
        { key: 'reorder_threshold', header: t('inventory.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'is_low', header: t('inventory.exportCols.lowStock'), value: (r) => (r.is_low ? t('common.yes') : t('common.no')) },
    ];
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2", children: [_jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('inventory.search.processed') }), _jsx(ExportMenu, { filename: "processed-stock", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => processedMaterials.stock.list(p), list.search ? { search: list.search } : {}) })] }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: ChefHat, title: t('inventory.empty.processed'), description: t('inventory.empty.processedDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }));
}
