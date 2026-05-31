import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Factory, PlayCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
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
    const { t } = useTranslation();
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
            toast.success(t('production.recorded'));
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
        { key: 'sched', header: t('production.columns.scheduled'), render: (r) => formatDate(r.scheduled_for) },
        { key: 'product', header: t('production.columns.product'), render: (r) => (_jsxs("div", { children: [_jsx("p", { className: "font-medium", children: r.product_name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: r.product_sku })] })) },
        { key: 'qty', header: t('production.columns.quantity'), align: 'right', render: (r) => formatNumber(r.quantity, 2) },
        { key: 'cost', header: t('production.columns.cost'), align: 'right', render: (r) => formatMoney(r.cost) },
        { key: 'status', header: t('production.columns.status'), render: (r) => {
                const cls = r.status === 'completed' ? 'badge-green'
                    : r.status === 'planned' ? 'badge-blue'
                        : 'badge-gray';
                const label = r.status === 'completed' ? t('production.statuses.completed')
                    : r.status === 'planned' ? t('production.statuses.planned')
                        : r.status;
                return _jsx("span", { className: cls, children: label });
            } },
        { key: 'when', header: t('production.columns.completed'), render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
        { key: 'by', header: t('production.columns.by'), render: (r) => r.created_by_name ?? '—' },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })) },
    ];
    const exportColumns = [
        { key: 'scheduled_for', header: t('production.exportCols.scheduled'), value: (r) => r.scheduled_for },
        { key: 'completed_at', header: t('production.exportCols.completed'), value: (r) => r.completed_at ?? '' },
        { key: 'product_sku', header: t('production.exportCols.productSku'), value: (r) => r.product_sku },
        { key: 'product_name', header: t('production.exportCols.product'), value: (r) => r.product_name },
        { key: 'quantity', header: t('production.exportCols.quantity'), value: (r) => Number(r.quantity) },
        { key: 'cost', header: t('production.exportCols.cost'), value: (r) => Number(r.cost) },
        { key: 'status', header: t('production.exportCols.status'), value: (r) => r.status },
        { key: 'created_by', header: t('production.exportCols.by'), value: (r) => r.created_by_name ?? '' },
        { key: 'notes', header: t('production.exportCols.notes'), value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('production.title'), subtitle: t('production.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "production-runs", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => production.runs.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: () => setOpen(true), className: "btn-primary", children: [_jsx(PlayCircle, { size: 16 }), " ", t('production.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('production.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: Factory, title: t('production.emptyTitle'), description: t('production.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: t('production.newTitle'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !productId || !qty || execute.isPending, onClick: () => execute.mutate(), children: execute.isPending ? t('production.footer.recording') : t('production.footer.record') })] }), children: _jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('production.fields.product') }), _jsxs("select", { className: "input", value: productId, onChange: (e) => setProductId(e.target.value), children: [_jsx("option", { value: "", children: t('common.select') }), products.data?.results.map((p) => (_jsx("option", { value: p.id, children: p.name }, p.id)))] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('production.fields.quantity') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: qty, onChange: (e) => setQty(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('production.fields.scheduledFor') }), _jsx("input", { type: "date", className: "input", value: scheduledFor, onChange: (e) => setScheduledFor(e.target.value) })] })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('production.fields.notesOptional') }), _jsx("textarea", { className: "input", rows: 2, value: notes, onChange: (e) => setNotes(e.target.value) })] }), _jsx("p", { className: "text-xs text-slate-500", children: t('production.footer.hint') })] }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('production.deleteTitle'), message: t('production.deleteMessage'), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
