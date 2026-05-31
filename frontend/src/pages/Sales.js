import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShoppingBag, Plus, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { catalog, sales } from '@/api/endpoints';
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
import { formatDateTime, formatMoney, formatNumber } from '@/lib/format';
export function SalesPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['sales'],
        fetcher: (p) => sales.list(p),
        deleter: (id) => sales.remove(id),
    });
    const products = useQuery({ queryKey: ['products-active'], queryFn: () => catalog.products.list({ page_size: 500, is_active: true }) });
    const paymentMethods = useQuery({ queryKey: ['pay-methods'], queryFn: sales.paymentMethods });
    const channels = useQuery({ queryKey: ['sale-channels'], queryFn: sales.channels });
    const [open, setOpen] = useState(false);
    const [viewing, setViewing] = useState(null);
    const [toDelete, setToDelete] = useState(null);
    // Cart state
    const [cart, setCart] = useState([]);
    const [paymentMethod, setPaymentMethod] = useState('cash');
    const [channel, setChannel] = useState('counter');
    const [discount, setDiscount] = useState('0');
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [notes, setNotes] = useState('');
    const [addProductId, setAddProductId] = useState('');
    const total = useMemo(() => {
        const subtotal = cart.reduce((acc, l) => acc + l.quantity * l.unit_price, 0);
        return Math.max(0, subtotal - Number(discount || 0));
    }, [cart, discount]);
    const submit = useMutation({
        mutationFn: () => sales.record({
            items: cart.map((l) => ({ product: l.product.id, quantity: l.quantity, unit_price: l.unit_price })),
            payment_method: paymentMethod,
            channel,
            discount: Number(discount || 0),
            customer_name: customerName,
            customer_phone: customerPhone,
            notes,
        }),
        onSuccess: (sale) => {
            toast.success(t('sales.recorded', { number: sale.receipt_number }));
            qc.invalidateQueries({ queryKey: ['sales'] });
            qc.invalidateQueries({ queryKey: ['stock'] });
            setOpen(false);
            setCart([]);
            setDiscount('0');
            setCustomerName('');
            setCustomerPhone('');
            setNotes('');
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function addToCart() {
        const product = products.data?.results.find((p) => p.id === addProductId);
        if (!product)
            return;
        setCart((prev) => {
            const existing = prev.find((l) => l.product.id === product.id);
            if (existing) {
                return prev.map((l) => l.product.id === product.id ? { ...l, quantity: l.quantity + 1 } : l);
            }
            return [...prev, { product, quantity: 1, unit_price: Number(product.selling_price) }];
        });
        setAddProductId('');
    }
    function removeLine(id) { setCart((p) => p.filter((l) => l.product.id !== id)); }
    function updateLine(id, patch) {
        setCart((p) => p.map((l) => l.product.id === id ? { ...l, ...patch } : l));
    }
    const columns = [
        { key: 'when', header: t('sales.columns.when'), render: (r) => formatDateTime(r.occurred_at) },
        { key: 'rcpt', header: t('sales.columns.receipt'), render: (r) => _jsx("span", { className: "font-mono text-xs", children: r.receipt_number }) },
        { key: 'customer', header: t('sales.columns.customer'), render: (r) => r.customer_name || '—' },
        { key: 'pay', header: t('sales.columns.payment'), render: (r) => _jsx("span", { className: "badge-blue", children: r.payment_method_display }) },
        { key: 'channel', header: t('sales.columns.channel'), render: (r) => _jsx("span", { className: "badge-gray", children: r.channel_display }) },
        { key: 'total', header: t('sales.columns.total'), align: 'right', render: (r) => _jsx("span", { className: "font-semibold", children: formatMoney(r.total) }) },
        { key: 'profit', header: t('sales.columns.profit'), align: 'right', render: (r) => _jsx("span", { className: "text-emerald-700", children: formatMoney(r.profit) }) },
        { key: 'actions', header: '', align: 'right', render: (r) => (_jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })) },
    ];
    const exportColumns = [
        { key: 'occurred_at', header: t('sales.exportCols.when'), value: (r) => r.occurred_at },
        { key: 'receipt_number', header: t('sales.exportCols.receipt'), value: (r) => r.receipt_number },
        { key: 'customer_name', header: t('sales.exportCols.customer'), value: (r) => r.customer_name },
        { key: 'customer_phone', header: t('sales.exportCols.phone'), value: (r) => r.customer_phone },
        { key: 'payment_method', header: t('sales.exportCols.paymentMethod'), value: (r) => r.payment_method_display },
        { key: 'channel', header: t('sales.exportCols.channel'), value: (r) => r.channel_display },
        { key: 'item_count', header: t('sales.exportCols.items'), value: (r) => r.items.length },
        { key: 'subtotal', header: t('sales.exportCols.subtotal'), value: (r) => Number(r.subtotal) },
        { key: 'discount', header: t('sales.exportCols.discount'), value: (r) => Number(r.discount) },
        { key: 'total', header: t('sales.exportCols.total'), value: (r) => Number(r.total) },
        { key: 'cost_of_goods', header: t('sales.exportCols.cogs'), value: (r) => Number(r.cost_of_goods) },
        { key: 'profit', header: t('sales.exportCols.profit'), value: (r) => Number(r.profit) },
        { key: 'served_by', header: t('sales.exportCols.servedBy'), value: (r) => r.served_by_name ?? '' },
        { key: 'notes', header: t('sales.exportCols.notes'), value: (r) => r.notes },
    ];
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('sales.title'), subtitle: t('sales.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "sales", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => sales.list(p), list.search ? { search: list.search } : {}) }), _jsxs("button", { onClick: () => setOpen(true), className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('sales.new')] })] }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('sales.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, onRowClick: (r) => setViewing(r), empty: _jsx(EmptyState, { icon: ShoppingBag, title: t('sales.emptyTitle') }) }), list.data && _jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage })] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: t('sales.new'), size: "xl", footer: _jsxs(_Fragment, { children: [_jsxs("div", { className: "mr-auto text-sm text-slate-500", children: [t('sales.footer.subtotal', { value: formatMoney(cart.reduce((a, l) => a + l.quantity * l.unit_price, 0)) }), Number(discount) > 0 && _jsxs(_Fragment, { children: [" \u00B7 ", t('sales.footer.discount', { value: formatMoney(Number(discount)) })] }), _jsx("span", { className: "ml-3 text-base text-slate-900 font-semibold", children: t('sales.footer.total', { value: formatMoney(total) }) })] }), _jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: cart.length === 0 || submit.isPending, onClick: () => submit.mutate(), children: submit.isPending ? t('sales.footer.recording') : t('sales.footer.record') })] }), children: _jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-6", children: [_jsxs("div", { className: "lg:col-span-2 space-y-3", children: [_jsxs("div", { className: "flex gap-2", children: [_jsxs("select", { className: "input flex-1", value: addProductId, onChange: (e) => setAddProductId(e.target.value), children: [_jsx("option", { value: "", children: t('sales.cart.addProductPlaceholder') }), products.data?.results.map((p) => (_jsxs("option", { value: p.id, children: [p.name, " \u00B7 ", formatMoney(p.selling_price)] }, p.id)))] }), _jsxs("button", { className: "btn-primary", onClick: addToCart, disabled: !addProductId, children: [_jsx(Plus, { size: 16 }), " ", t('common.add')] })] }), _jsxs("ul", { className: "border border-slate-200 rounded-md divide-y divide-slate-100", children: [cart.length === 0 && (_jsx("li", { className: "px-4 py-6 text-sm text-slate-400 text-center", children: t('sales.cart.empty') })), cart.map((l) => (_jsxs("li", { className: "grid grid-cols-12 gap-2 px-3 py-2 items-center", children: [_jsxs("div", { className: "col-span-5", children: [_jsx("p", { className: "text-sm font-medium", children: l.product.name }), _jsx("p", { className: "text-xs text-slate-500 font-mono", children: l.product.sku })] }), _jsxs("div", { className: "col-span-3", children: [_jsx("label", { className: "text-xs text-slate-500", children: t('sales.cart.qty') }), _jsx("input", { type: "number", min: "1", step: "0.01", className: "input py-1.5", value: l.quantity, onChange: (e) => updateLine(l.product.id, { quantity: Number(e.target.value) }) })] }), _jsxs("div", { className: "col-span-3", children: [_jsx("label", { className: "text-xs text-slate-500", children: t('sales.cart.unitPrice') }), _jsx("input", { type: "number", step: "0.01", className: "input py-1.5", value: l.unit_price, onChange: (e) => updateLine(l.product.id, { unit_price: Number(e.target.value) }) })] }), _jsx("div", { className: "col-span-1 text-right", children: _jsx("button", { className: "text-red-500 hover:text-red-700", onClick: () => removeLine(l.product.id), children: _jsx(X, { size: 16 }) }) }), _jsx("div", { className: "col-span-12 text-right text-sm font-semibold text-slate-700", children: t('sales.cart.lineTotal', { value: formatMoney(l.quantity * l.unit_price) }) })] }, l.product.id)))] })] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.paymentMethod') }), _jsx("select", { className: "input", value: paymentMethod, onChange: (e) => setPaymentMethod(e.target.value), children: paymentMethods.data?.map((m) => _jsx("option", { value: m.value, children: m.label }, m.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.channel') }), _jsx("select", { className: "input", value: channel, onChange: (e) => setChannel(e.target.value), children: channels.data?.map((c) => _jsx("option", { value: c.value, children: c.label }, c.value)) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.discount') }), _jsx("input", { type: "number", step: "0.01", className: "input", value: discount, onChange: (e) => setDiscount(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.customerName') }), _jsx("input", { className: "input", value: customerName, onChange: (e) => setCustomerName(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.customerPhone') }), _jsx("input", { className: "input", value: customerPhone, onChange: (e) => setCustomerPhone(e.target.value) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('sales.fields.notes') }), _jsx("textarea", { className: "input", rows: 2, value: notes, onChange: (e) => setNotes(e.target.value) })] })] })] }) }), _jsx(Modal, { open: !!viewing, onClose: () => setViewing(null), title: viewing ? t('sales.details.receipt', { number: viewing.receipt_number }) : '', size: "lg", children: viewing && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-3 text-sm", children: [_jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.when') }), " ", formatDateTime(viewing.occurred_at)] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.payment') }), " ", viewing.payment_method_display] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.channel') }), " ", viewing.channel_display] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.servedBy') }), " ", viewing.served_by_name ?? '—'] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.customer') }), " ", viewing.customer_name || '—'] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: t('sales.details.phone') }), " ", viewing.customer_phone || '—'] })] }), _jsxs("table", { className: "table-base", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: t('sales.details.product') }), _jsx("th", { className: "text-right", children: t('sales.details.qty') }), _jsx("th", { className: "text-right", children: t('sales.details.unit') }), _jsx("th", { className: "text-right", children: t('sales.details.total') })] }) }), _jsx("tbody", { children: viewing.items.map((it) => (_jsxs("tr", { children: [_jsx("td", { children: it.product_name }), _jsx("td", { className: "text-right", children: formatNumber(it.quantity, 2) }), _jsx("td", { className: "text-right", children: formatMoney(it.unit_price) }), _jsx("td", { className: "text-right font-medium", children: formatMoney(it.line_total) })] }, it.id))) })] }), _jsxs("div", { className: "text-right space-y-1 text-sm", children: [_jsxs("div", { children: [t('sales.details.subtotal'), " ", _jsx("strong", { children: formatMoney(viewing.subtotal) })] }), _jsxs("div", { children: [t('sales.details.discount'), " ", _jsx("strong", { children: formatMoney(viewing.discount) })] }), _jsxs("div", { className: "text-base", children: [t('sales.details.totalLabel'), " ", _jsx("strong", { children: formatMoney(viewing.total) })] }), _jsxs("div", { className: "text-emerald-700", children: [t('sales.details.profit'), " ", _jsx("strong", { children: formatMoney(viewing.profit) })] })] })] })) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('sales.deleteTitle'), message: t('sales.deleteMessage'), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (!toDelete)
                        return;
                    list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
                } })] }));
}
