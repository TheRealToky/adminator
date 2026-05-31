import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Factory, PlayCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { catalog, production } from '@/api/endpoints';
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
import { formatDate, formatDateTime, formatMoney, formatNumber } from '@/lib/format';
export function ProductionPage() {
    const qc = useQueryClient();
    const list = useCrudList({
        queryKey: ['production-runs'],
        fetcher: (p) => production.runs.list(p),
        deleter: (id) => production.runs.remove(id),
    });
    const products = useQuery({
        queryKey: ['products-all'],
        queryFn: () => catalog.products.list({ page_size: 500, is_active: true }),
    });
    const [open, setOpen] = useState(false);
    const [productId, setProductId] = useState('');
    const [qty, setQty] = useState('');
    const [scheduledFor, setScheduledFor] = useState(new Date().toISOString().slice(0, 10));
    const [notes, setNotes] = useState('');
    const [toDelete, setToDelete] = useState(null);
    const execute = useMutation({
        mutationFn: () => production.runs.execute({
            product: productId,
            quantity: Number(qty),
            scheduled_for: scheduledFor,
            notes,
        }),
        onSuccess: () => {
            toast.success('Production run recorded.');
            qc.invalidateQueries({ queryKey: ['production-runs'] });
            qc.invalidateQueries({ queryKey: ['stock'] });
            qc.invalidateQueries({ queryKey: ['movements'] });
            setOpen(false);
            setProductId('');
            setQty('');
            setNotes('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const columns = [
        { key: 'sched', header: 'Scheduled', render: (r) => formatDate(r.scheduled_for) },
        { key: 'product', header: 'Product', render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.product_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.product_sku })] })) },
        { key: 'qty', header: 'Quantity', align: 'right', render: (r) => formatNumber(r.quantity, 2) },
        { key: 'cost', header: 'Cost', align: 'right', render: (r) => formatMoney(r.cost) },
        { key: 'status', header: 'Status', render: (r) => {
                const cls = r.status === 'completed' ? 'badge-green'
                    : r.status === 'planned' ? 'badge-blue'
                        : 'badge-gray';
                return _jsx("span", { className: cls, children: r.status });
            } },
        { key: 'when', header: 'Completed', render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
        { key: 'by', header: 'By', render: (r) => r.created_by_name ?? '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })) },
    ];
    const exportColumns = [
        { key: 'scheduled_for', header: 'Scheduled', value: (r) => r.scheduled_for },
        { key: 'completed_at', header: 'Completed', value: (r) => r.completed_at ?? '' },
        { key: 'product_sku', header: 'Product SKU', value: (r) => r.product_sku },
        { key: 'product_name', header: 'Product', value: (r) => r.product_name },
        { key: 'quantity', header: 'Quantity', value: (r) => Number(r.quantity) },
        { key: 'cost', header: 'Cost', value: (r) => Number(r.cost) },
        { key: 'status', header: 'Status', value: (r) => r.status },
        { key: 'created_by', header: 'By', value: (r) => r.created_by_name ?? '' },
        { key: 'notes', header: 'Notes', value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Production", subtitle: "Bake & cook runs \u2014 automatically consumes raw materials", actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "production-runs", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => production.runs.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: () => setOpen(true), className: "btn-primary", children: [_jsx(PlayCircle, { size: 16 }), " New run"] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: "Search by product\u2026" }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Factory, title: "No production runs yet", description: "Record what you bake to keep stock and costs accurate." }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: "New production run", footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: "Cancel" }), _jsx("button", { className: "btn-primary", disabled: !productId || !qty || execute.isPending, onClick: () => execute.mutate(), children: execute.isPending ? 'Recording…' : 'Record' })] }), children: _jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "Product" }), _jsxs("select", { className: "input", value: productId, onChange: (e) => setProductId(e.target.value), children: [_jsx("option", { value: "", children: "\u2014 Select \u2014" }), products.data?.results.map((p) => (_jsx("option", { value: p.id, children: p.name }, p.id)))] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: "Quantity" }), _jsx("input", { type: "number", step: "0.01", className: "input", value: qty, onChange: (e) => setQty(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Scheduled for" }), _jsx("input", { type: "date", className: "input", value: scheduledFor, onChange: (e) => setScheduledFor(e.target.value) })] })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: "Notes (optional)" }), _jsx("textarea", { className: "input", rows: 2, value: notes, onChange: (e) => setNotes(e.target.value) })] }), _jsx("p", { className: "text-xs text-slate-500", children: "Recording a run will deduct each ingredient from raw material stock based on the product's recipe." })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: "Delete this run?", message: "The run will be removed but related stock movements are preserved for audit.", confirmLabel: "Delete", loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
