import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Boxes, AlertTriangle, History, Sliders, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';
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
import { formatQuantity, formatMoney, formatDateTime } from '@/lib/format';
export function InventoryPage() {
    const { t } = useTranslation();
    const [tab, setTab] = useState('all');
    const [adjustOpen, setAdjustOpen] = useState(null);
    const [pmAdjustOpen, setPmAdjustOpen] = useState(null);
    const [writeOffOpen, setWriteOffOpen] = useState(null);
    const [pmWriteOffOpen, setPmWriteOffOpen] = useState(null);
    const tabs = [
        { key: 'all', label: t('inventory.tabs.all'), icon: Boxes },
        { key: 'low', label: t('inventory.tabs.low'), icon: AlertTriangle },
        { key: 'movements', label: t('inventory.tabs.movements'), icon: History },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('inventory.title'), subtitle: t('inventory.subtitle') }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header gap-2 flex-wrap", children: _jsx("div", { className: "flex gap-1", children: tabs.map(({ key, label, icon: Icon }) => (_jsxs("button", { onClick: () => setTab(key), className: `px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: [_jsx(Icon, { size: 14 }), " ", label] }, key))) }) }), tab === 'all' && (_jsx(CombinedStockTab, { onAdjust: setAdjustOpen, onPmAdjust: setPmAdjustOpen, onWriteOff: setWriteOffOpen, onPmWriteOff: setPmWriteOffOpen })), tab === 'low' && (_jsx(CombinedStockTab, { lowOnly: true, onAdjust: setAdjustOpen, onPmAdjust: setPmAdjustOpen, onWriteOff: setWriteOffOpen, onPmWriteOff: setPmWriteOffOpen })), tab === 'movements' && _jsx(MovementsTab, {})] }), _jsx(AdjustModal, { stock: adjustOpen, onClose: () => setAdjustOpen(null) }), _jsx(ProcessedAdjustModal, { stock: pmAdjustOpen, onClose: () => setPmAdjustOpen(null) }), _jsx(WriteOffModal, { stock: writeOffOpen, onClose: () => setWriteOffOpen(null) }), _jsx(ProcessedWriteOffModal, { stock: pmWriteOffOpen, onClose: () => setPmWriteOffOpen(null) })] }));
}
// ── Tabs ──────────────────────────────────────────────────────────────────
const PAGE_SIZE = 25;
function tagProcessed(rows) {
    return rows.map((r) => ({ ...r, kind: 'processed' }));
}
/** Fetch products, raw materials, and processed materials and merge them. */
async function fetchCombinedStock(lowOnly) {
    const [stock, processed] = await Promise.all([
        lowOnly
            ? inventory.stock.low().then((r) => r.results)
            : fetchAllPaginated((p) => inventory.stock.list(p)),
        lowOnly
            ? processedMaterials.stock.low().then((r) => r.results)
            : fetchAllPaginated((p) => processedMaterials.stock.list(p)),
    ]);
    const rows = [...stock, ...tagProcessed(processed)];
    rows.sort((a, b) => a.item_name.localeCompare(b.item_name));
    return rows;
}
function useStockColumns(onAdjust, onPmAdjust, onWriteOff, onPmWriteOff) {
    const { t } = useTranslation();
    return [
        { key: 'name', header: t('inventory.columns.item'), render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.item_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.item_sku })] })) },
        { key: 'kind', header: t('inventory.columns.type'), render: (r) => r.kind === 'product'
                ? _jsx("span", { className: "badge-blue", children: t('inventory.badges.product') })
                : r.kind === 'processed'
                    ? _jsx("span", { className: "badge-yellow", children: t('inventory.badges.processed') })
                    : _jsx("span", { className: "badge-gray", children: t('inventory.badges.material') })
        },
        { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (_jsxs("span", { className: r.is_low ? 'text-red-600 font-semibold' : 'font-medium', children: [formatQuantity(r.quantity), " ", r.item_unit] })) },
        { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => formatQuantity(r.reorder_threshold) },
        { key: 'status', header: t('inventory.columns.status'), render: (r) => r.is_low
                ? _jsx("span", { className: "badge-red", children: t('inventory.badges.low') })
                : _jsx("span", { className: "badge-green", children: t('inventory.badges.ok') })
        },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsxs("button", { className: "btn-secondary px-2 py-1 text-xs", onClick: () => (r.kind === 'processed' ? onPmAdjust(r) : onAdjust(r)), children: [_jsx(Sliders, { size: 12 }), " ", t('inventory.actions.adjust')] }), _jsxs("button", { className: "btn-ghost px-2 py-1 text-xs text-red-600", title: t('inventory.actions.writeOff'), disabled: Number(r.quantity) <= 0, onClick: () => (r.kind === 'processed' ? onPmWriteOff(r) : onWriteOff(r)), children: [_jsx(Trash2, { size: 12 }), " ", t('inventory.actions.writeOff')] })] })) },
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
function CombinedStockTab({ lowOnly = false, onAdjust, onPmAdjust, onWriteOff, onPmWriteOff, }) {
    const { t } = useTranslation();
    const [search, setSearch] = useState('');
    const [kind, setKind] = useState('all');
    const [page, setPage] = useState(1);
    const { data, isLoading } = useQuery({
        queryKey: lowOnly ? ['stock-combined', 'low'] : ['stock-combined', 'all'],
        queryFn: () => fetchCombinedStock(lowOnly),
    });
    const columns = useStockColumns(onAdjust, onPmAdjust, onWriteOff, onPmWriteOff);
    const exportColumns = useStockExportColumns();
    const kindFilters = [
        { key: 'all', label: t('inventory.filter.all') },
        { key: 'product', label: t('inventory.filter.products') },
        { key: 'raw_material', label: t('inventory.filter.materials') },
        { key: 'processed', label: t('inventory.filter.processed') },
    ];
    const filtered = useMemo(() => {
        let rows = data ?? [];
        if (kind !== 'all')
            rows = rows.filter((r) => r.kind === kind);
        const q = search.trim().toLowerCase();
        if (q) {
            rows = rows.filter((r) => r.item_name.toLowerCase().includes(q) || r.item_sku.toLowerCase().includes(q));
        }
        return rows;
    }, [data, search, kind]);
    const pageRows = useMemo(() => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [filtered, page]);
    const empty = lowOnly
        ? _jsx(EmptyState, { icon: AlertTriangle, title: t('inventory.empty.low'), description: t('inventory.empty.lowDescription') })
        : _jsx(EmptyState, { icon: Boxes, title: t('inventory.empty.stock'), description: t('inventory.empty.stockDescription') });
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "px-5 pt-3 flex items-center justify-between gap-2 flex-wrap", children: [_jsxs("div", { className: "flex items-center gap-3 flex-wrap", children: [_jsx(SearchBar, { value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: t('inventory.search.all') }), _jsx("div", { className: "flex gap-1", children: kindFilters.map(({ key, label }) => (_jsx("button", { onClick: () => { setKind(key); setPage(1); }, className: `px-2.5 py-1 rounded-md text-xs font-medium ${kind === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`, children: label }, key))) })] }), _jsx(ExportMenu, { filename: lowOnly ? 'low-stock' : 'stock', columns: exportColumns, fetchRows: async () => filtered })] }), _jsx(DataTable, { columns: columns, data: isLoading ? undefined : pageRows, loading: isLoading, rowKey: (r) => `${r.kind}-${r.id}`, empty: empty }), filtered.length > 0 && (_jsx(Pagination, { page: page, pageSize: PAGE_SIZE, total: filtered.length, onChange: setPage }))] }));
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
        { key: 'delta', header: t('inventory.columns.delta'), align: 'right', render: (r) => (_jsxs("span", { className: Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold', children: [Number(r.quantity_delta) > 0 ? '+' : '', formatQuantity(r.quantity_delta), " ", r.item_unit] })) },
        { key: 'balance', header: t('inventory.columns.after'), align: 'right', render: (r) => `${formatQuantity(r.balance_after)} ${r.item_unit}` },
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
            qc.invalidateQueries({ queryKey: ['stock-combined'] });
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
                        qty: formatQuantity(stock.quantity),
                        unit: stock.item_unit,
                    }),
                } }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('inventory.adjust.delta', { unit: stock.item_unit }) }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: delta, onChange: (e) => setDelta(e.target.value), autoFocus: true })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('common.noteOptional') }), _jsx("textarea", { className: "input", rows: 2, value: note, onChange: (e) => setNote(e.target.value) })] })] })] }));
}
// ── Adjust modal (processed materials) ───────────────────────────────────
function ProcessedAdjustModal({ stock, onClose, }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const [delta, setDelta] = useState('');
    const [note, setNote] = useState('');
    const mutate = useMutation({
        mutationFn: () => processedMaterials.stock.adjust({
            processed_material: stock.processed_material,
            quantity_delta: Number(delta),
            note,
        }),
        onSuccess: () => {
            toast.success(t('processedMaterials.adjust.recorded'));
            qc.invalidateQueries({ queryKey: ['processed-stock'] });
            qc.invalidateQueries({ queryKey: ['stock-combined'] });
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
            qc.invalidateQueries({ queryKey: ['processed-movements'] });
            onClose();
            setDelta('');
            setNote('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!stock)
        return null;
    return (_jsxs(Modal, { open: !!stock, onClose: onClose, title: t('processedMaterials.adjust.title', { name: stock.item_name }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !delta || Number(delta) === 0 || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending ? t('common.saving') : t('common.apply') })] }), children: [_jsx("p", { className: "text-sm text-slate-500 mb-3", dangerouslySetInnerHTML: {
                    __html: t('processedMaterials.adjust.currentOnHand', {
                        qty: formatQuantity(stock.quantity),
                        unit: stock.item_unit,
                    }),
                } }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('processedMaterials.adjust.delta', { unit: stock.item_unit }) }), _jsx("input", { type: "number", step: "0.0001", className: "input", value: delta, onChange: (e) => setDelta(e.target.value), autoFocus: true })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('common.noteOptional') }), _jsx("textarea", { className: "input", rows: 2, value: note, onChange: (e) => setNote(e.target.value) })] })] })] }));
}
// ── Write-off modal (products / raw materials) ───────────────────────────
function WriteOffModal({ stock, onClose }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const [quantity, setQuantity] = useState('');
    const [note, setNote] = useState('');
    const [reference, setReference] = useState('');
    const mutate = useMutation({
        mutationFn: () => inventory.stock.writeOff({
            product: stock?.kind === 'product' ? stock.product : undefined,
            raw_material: stock?.kind === 'raw_material' ? stock.raw_material : undefined,
            quantity: Number(quantity),
            note,
            reference,
        }),
        onSuccess: () => {
            const qty = Number(quantity);
            const expense = qty * Number(stock?.item_unit_cost ?? 0);
            toast.success(expense > 0
                ? t('inventory.writeOff.recorded', {
                    qty: formatQuantity(qty),
                    unit: stock?.item_unit ?? '',
                    name: stock?.item_name ?? '',
                })
                : t('inventory.writeOff.recordedNoCost', {
                    qty: formatQuantity(qty),
                    unit: stock?.item_unit ?? '',
                    name: stock?.item_name ?? '',
                }));
            qc.invalidateQueries({ queryKey: ['stock'] });
            qc.invalidateQueries({ queryKey: ['stock-combined'] });
            qc.invalidateQueries({ queryKey: ['stock-low'] });
            qc.invalidateQueries({ queryKey: ['movements'] });
            qc.invalidateQueries({ queryKey: ['expenses'] });
            qc.invalidateQueries({ queryKey: ['dashboard'] });
            onClose();
            setQuantity('');
            setNote('');
            setReference('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!stock)
        return null;
    const onHand = Number(stock.quantity);
    const unitCost = Number(stock.item_unit_cost || 0);
    const qty = Number(quantity) || 0;
    const exceedsStock = qty > onHand;
    const expense = qty * unitCost;
    return (_jsxs(Modal, { open: !!stock, onClose: onClose, title: t('inventory.writeOff.title', { name: stock.item_name }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !quantity || qty <= 0 || exceedsStock || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending ? t('inventory.writeOff.submitting') : t('inventory.writeOff.submit') })] }), children: [_jsx("p", { className: "text-sm text-slate-500 mb-3", children: unitCost > 0 ? (_jsx(Trans, { i18nKey: "inventory.writeOff.lead", values: { cost: formatMoney(unitCost), unit: stock.item_unit }, components: { 1: _jsx("strong", {}) } })) : (t('inventory.writeOff.leadZeroCost')) }), _jsx("p", { className: "text-sm text-slate-500 mb-3", dangerouslySetInnerHTML: {
                    __html: t('inventory.writeOff.currentOnHand', {
                        qty: formatQuantity(onHand),
                        unit: stock.item_unit,
                    }),
                } }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('inventory.writeOff.quantity', { unit: stock.item_unit }) }), _jsx("input", { autoFocus: true, type: "number", step: "0.0001", min: "0", max: onHand, className: "input", value: quantity, onChange: (e) => setQuantity(e.target.value) }), exceedsStock && (_jsx("p", { className: "text-xs text-red-600 mt-1", children: t('inventory.writeOff.exceedsOnHand', {
                                    qty: formatQuantity(onHand),
                                    unit: stock.item_unit,
                                }) }))] }), _jsxs("div", { className: "rounded-md bg-slate-50 border border-slate-200 px-3 py-2 flex items-center justify-between", children: [_jsx("span", { className: "text-xs text-slate-600", children: t('inventory.writeOff.expenseToBook') }), _jsx("span", { className: "text-sm font-semibold tabular-nums", children: formatMoney(expense) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('inventory.writeOff.reason') }), _jsx("textarea", { className: "input", rows: 2, placeholder: t('inventory.writeOff.reasonPlaceholder'), value: note, onChange: (e) => setNote(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('inventory.writeOff.reference') }), _jsx("input", { className: "input", value: reference, onChange: (e) => setReference(e.target.value) })] })] })] }));
}
// ── Write-off modal (processed materials) ────────────────────────────────
function ProcessedWriteOffModal({ stock, onClose, }) {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const [quantity, setQuantity] = useState('');
    const [note, setNote] = useState('');
    const [reference, setReference] = useState('');
    const mutate = useMutation({
        mutationFn: () => processedMaterials.stock.writeOff({
            processed_material: stock.processed_material,
            quantity: Number(quantity),
            note,
            reference,
        }),
        onSuccess: () => {
            const qty = Number(quantity);
            const expense = qty * Number(stock?.item_unit_cost ?? 0);
            toast.success(expense > 0
                ? t('processedMaterials.writeOff.recorded', {
                    qty: formatQuantity(qty),
                    unit: stock?.item_unit ?? '',
                    name: stock?.item_name ?? '',
                })
                : t('processedMaterials.writeOff.recordedNoCost', {
                    qty: formatQuantity(qty),
                    unit: stock?.item_unit ?? '',
                    name: stock?.item_name ?? '',
                }));
            qc.invalidateQueries({ queryKey: ['processed-stock'] });
            qc.invalidateQueries({ queryKey: ['stock-combined'] });
            qc.invalidateQueries({ queryKey: ['processed-materials'] });
            qc.invalidateQueries({ queryKey: ['processed-movements'] });
            qc.invalidateQueries({ queryKey: ['expenses'] });
            qc.invalidateQueries({ queryKey: ['dashboard'] });
            onClose();
            setQuantity('');
            setNote('');
            setReference('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    if (!stock)
        return null;
    const onHand = Number(stock.quantity);
    const unitCost = Number(stock.item_unit_cost || 0);
    const qty = Number(quantity) || 0;
    const exceedsStock = qty > onHand;
    const expense = qty * unitCost;
    return (_jsxs(Modal, { open: !!stock, onClose: onClose, title: t('processedMaterials.writeOff.title', { name: stock.item_name }), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: onClose, children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !quantity || qty <= 0 || exceedsStock || mutate.isPending, onClick: () => mutate.mutate(), children: mutate.isPending
                        ? t('processedMaterials.writeOff.submitting')
                        : t('processedMaterials.writeOff.submit') })] }), children: [_jsx("p", { className: "text-sm text-slate-500 mb-3", children: unitCost > 0 ? (_jsx(Trans, { i18nKey: "processedMaterials.writeOff.lead", values: { cost: formatMoney(unitCost), unit: stock.item_unit }, components: { 1: _jsx("strong", {}) } })) : (t('processedMaterials.writeOff.leadZeroCost')) }), _jsx("p", { className: "text-sm text-slate-500 mb-3", dangerouslySetInnerHTML: {
                    __html: t('processedMaterials.writeOff.currentOnHand', {
                        qty: formatQuantity(onHand),
                        unit: stock.item_unit,
                    }),
                } }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('processedMaterials.writeOff.quantity', { unit: stock.item_unit }) }), _jsx("input", { autoFocus: true, type: "number", step: "0.0001", min: "0", max: onHand, className: "input", value: quantity, onChange: (e) => setQuantity(e.target.value) }), exceedsStock && (_jsx("p", { className: "text-xs text-red-600 mt-1", children: t('processedMaterials.writeOff.exceedsOnHand', {
                                    qty: formatQuantity(onHand),
                                    unit: stock.item_unit,
                                }) }))] }), _jsxs("div", { className: "rounded-md bg-slate-50 border border-slate-200 px-3 py-2 flex items-center justify-between", children: [_jsx("span", { className: "text-xs text-slate-600", children: t('processedMaterials.writeOff.expenseToBook') }), _jsx("span", { className: "text-sm font-semibold tabular-nums", children: formatMoney(expense) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('processedMaterials.writeOff.reason') }), _jsx("textarea", { className: "input", rows: 2, placeholder: t('processedMaterials.writeOff.reasonPlaceholder'), value: note, onChange: (e) => setNote(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('processedMaterials.writeOff.reference') }), _jsx("input", { className: "input", value: reference, onChange: (e) => setReference(e.target.value) })] })] })] }));
}
