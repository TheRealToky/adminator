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
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { formatDateTime, formatMoney, formatNumber } from '@/lib/format';
import type { Product, Sale } from '@/api/types';

interface CartLine { product: Product; quantity: number; unit_price: number; }

export function SalesPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Sale>({
    queryKey: ['sales'],
    fetcher: (p) => sales.list(p),
    deleter: (id) => sales.remove(id),
  });
  const products = useQuery({ queryKey: ['products-active'], queryFn: () => catalog.products.list({ page_size: 500, is_active: true }) });
  const paymentMethods = useQuery({ queryKey: ['pay-methods'], queryFn: sales.paymentMethods });
  const channels = useQuery({ queryKey: ['sale-channels'], queryFn: sales.channels });

  const [open, setOpen] = useState(false);
  const [viewing, setViewing] = useState<Sale | null>(null);
  const [toDelete, setToDelete] = useState<Sale | null>(null);

  // Cart state
  const [cart, setCart] = useState<CartLine[]>([]);
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
      setCart([]); setDiscount('0'); setCustomerName(''); setCustomerPhone(''); setNotes('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function addToCart() {
    const product = products.data?.results.find((p) => p.id === addProductId);
    if (!product) return;
    setCart((prev) => {
      const existing = prev.find((l) => l.product.id === product.id);
      if (existing) {
        return prev.map((l) => l.product.id === product.id ? { ...l, quantity: l.quantity + 1 } : l);
      }
      return [...prev, { product, quantity: 1, unit_price: Number(product.selling_price) }];
    });
    setAddProductId('');
  }
  function removeLine(id: string) { setCart((p) => p.filter((l) => l.product.id !== id)); }
  function updateLine(id: string, patch: Partial<CartLine>) {
    setCart((p) => p.map((l) => l.product.id === id ? { ...l, ...patch } : l));
  }

  const columns: Column<Sale>[] = [
    { key: 'when', header: t('sales.columns.when'), render: (r) => formatDateTime(r.occurred_at) },
    { key: 'rcpt', header: t('sales.columns.receipt'), render: (r) => <span className="font-mono text-xs">{r.receipt_number}</span> },
    { key: 'customer', header: t('sales.columns.customer'), render: (r) => r.customer_name || '—' },
    { key: 'pay', header: t('sales.columns.payment'), render: (r) => <span className="badge-blue">{r.payment_method_display}</span> },
    { key: 'channel', header: t('sales.columns.channel'), render: (r) => <span className="badge-gray">{r.channel_display}</span> },
    { key: 'total', header: t('sales.columns.total'), align: 'right', render: (r) => <span className="font-semibold">{formatMoney(r.total)}</span> },
    { key: 'profit', header: t('sales.columns.profit'), align: 'right', render: (r) => <span className="text-emerald-700">{formatMoney(r.profit)}</span> },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}>
        <Trash2 size={14} />
      </button>
    )},
  ];

  const exportColumns: ExportColumn<Sale>[] = [
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

  return (
    <>
      <PageHeader
        title={t('sales.title')}
        subtitle={t('sales.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="sales"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => sales.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={() => setOpen(true)} className="btn-primary"><Plus size={16} /> {t('sales.new')}</button>
          </>
        }
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('sales.searchPlaceholder')} />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          onRowClick={(r) => setViewing(r)}
          empty={<EmptyState icon={ShoppingBag} title={t('sales.emptyTitle')} />}
        />
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />}
      </div>

      {/* New sale modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t('sales.new')}
        size="xl"
        footer={
          <>
            <div className="mr-auto text-sm text-slate-500">
              {t('sales.footer.subtotal', { value: formatMoney(cart.reduce((a, l) => a + l.quantity * l.unit_price, 0)) })}
              {Number(discount) > 0 && <> · {t('sales.footer.discount', { value: formatMoney(Number(discount)) })}</>}
              <span className="ml-3 text-base text-slate-900 font-semibold">{t('sales.footer.total', { value: formatMoney(total) })}</span>
            </div>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={cart.length === 0 || submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending ? t('sales.footer.recording') : t('sales.footer.record')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cart */}
          <div className="lg:col-span-2 space-y-3">
            <div className="flex gap-2">
              <select className="input flex-1" value={addProductId} onChange={(e) => setAddProductId(e.target.value)}>
                <option value="">{t('sales.cart.addProductPlaceholder')}</option>
                {products.data?.results.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} · {formatMoney(p.selling_price)}</option>
                ))}
              </select>
              <button className="btn-primary" onClick={addToCart} disabled={!addProductId}>
                <Plus size={16} /> {t('common.add')}
              </button>
            </div>

            <ul className="border border-slate-200 rounded-md divide-y divide-slate-100">
              {cart.length === 0 && (
                <li className="px-4 py-6 text-sm text-slate-400 text-center">{t('sales.cart.empty')}</li>
              )}
              {cart.map((l) => (
                <li key={l.product.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center">
                  <div className="col-span-5">
                    <p className="text-sm font-medium">{l.product.name}</p>
                    <p className="text-xs text-slate-500 font-mono">{l.product.sku}</p>
                  </div>
                  <div className="col-span-3">
                    <label className="text-xs text-slate-500">{t('sales.cart.qty')}</label>
                    <input
                      type="number" min="1" step="0.01" className="input py-1.5"
                      value={l.quantity}
                      onChange={(e) => updateLine(l.product.id, { quantity: Number(e.target.value) })}
                    />
                  </div>
                  <div className="col-span-3">
                    <label className="text-xs text-slate-500">{t('sales.cart.unitPrice')}</label>
                    <input
                      type="number" step="0.01" className="input py-1.5"
                      value={l.unit_price}
                      onChange={(e) => updateLine(l.product.id, { unit_price: Number(e.target.value) })}
                    />
                  </div>
                  <div className="col-span-1 text-right">
                    <button className="text-red-500 hover:text-red-700" onClick={() => removeLine(l.product.id)}>
                      <X size={16} />
                    </button>
                  </div>
                  <div className="col-span-12 text-right text-sm font-semibold text-slate-700">
                    {t('sales.cart.lineTotal', { value: formatMoney(l.quantity * l.unit_price) })}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Side panel */}
          <div className="space-y-3">
            <div>
              <label className="label">{t('sales.fields.paymentMethod')}</label>
              <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                {paymentMethods.data?.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">{t('sales.fields.channel')}</label>
              <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
                {channels.data?.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">{t('sales.fields.discount')}</label>
              <input type="number" step="0.01" className="input" value={discount} onChange={(e) => setDiscount(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('sales.fields.customerName')}</label>
              <input className="input" value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('sales.fields.customerPhone')}</label>
              <input className="input" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('sales.fields.notes')}</label>
              <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>
        </div>
      </Modal>

      {/* View sale details */}
      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing ? t('sales.details.receipt', { number: viewing.receipt_number }) : ''} size="lg">
        {viewing && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-slate-500">{t('sales.details.when')}</span> {formatDateTime(viewing.occurred_at)}</div>
              <div><span className="text-slate-500">{t('sales.details.payment')}</span> {viewing.payment_method_display}</div>
              <div><span className="text-slate-500">{t('sales.details.channel')}</span> {viewing.channel_display}</div>
              <div><span className="text-slate-500">{t('sales.details.servedBy')}</span> {viewing.served_by_name ?? '—'}</div>
              <div><span className="text-slate-500">{t('sales.details.customer')}</span> {viewing.customer_name || '—'}</div>
              <div><span className="text-slate-500">{t('sales.details.phone')}</span> {viewing.customer_phone || '—'}</div>
            </div>
            <table className="table-base">
              <thead>
                <tr>
                  <th>{t('sales.details.product')}</th>
                  <th className="text-right">{t('sales.details.qty')}</th>
                  <th className="text-right">{t('sales.details.unit')}</th>
                  <th className="text-right">{t('sales.details.total')}</th>
                </tr>
              </thead>
              <tbody>
                {viewing.items.map((it) => (
                  <tr key={it.id}>
                    <td>{it.product_name}</td>
                    <td className="text-right">{formatNumber(it.quantity, 2)}</td>
                    <td className="text-right">{formatMoney(it.unit_price)}</td>
                    <td className="text-right font-medium">{formatMoney(it.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-right space-y-1 text-sm">
              <div>{t('sales.details.subtotal')} <strong>{formatMoney(viewing.subtotal)}</strong></div>
              <div>{t('sales.details.discount')} <strong>{formatMoney(viewing.discount)}</strong></div>
              <div className="text-base">{t('sales.details.totalLabel')} <strong>{formatMoney(viewing.total)}</strong></div>
              <div className="text-emerald-700">{t('sales.details.profit')} <strong>{formatMoney(viewing.profit)}</strong></div>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('sales.deleteTitle')}
        message={t('sales.deleteMessage')}
        confirmLabel={t('common.delete')}
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (!toDelete) return;
          list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
        }}
      />
    </>
  );
}
