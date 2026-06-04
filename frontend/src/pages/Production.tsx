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
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { formatDate, formatDateTime, formatMoney, formatQuantity } from '@/lib/format';
import type { ProductionRun } from '@/api/types';

export function ProductionPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<ProductionRun>({
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
  const [toDelete, setToDelete] = useState<ProductionRun | null>(null);

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
      setOpen(false); setProductId(''); setQty(''); setNotes('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const columns: Column<ProductionRun>[] = [
    { key: 'sched', header: t('production.columns.scheduled'), render: (r) => formatDate(r.scheduled_for) },
    { key: 'product', header: t('production.columns.product'), render: (r) => (
      <div>
        <p className="font-medium">{r.product_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.product_sku}</p>
      </div>
    )},
    { key: 'qty', header: t('production.columns.quantity'), align: 'right', render: (r) => formatQuantity(r.quantity) },
    { key: 'cost', header: t('production.columns.cost'), align: 'right', render: (r) => formatMoney(r.cost) },
    { key: 'status', header: t('production.columns.status'), render: (r) => {
      const cls = r.status === 'completed' ? 'badge-green'
                : r.status === 'planned' ? 'badge-blue'
                : 'badge-gray';
      const label = r.status === 'completed' ? t('production.statuses.completed')
                  : r.status === 'planned' ? t('production.statuses.planned')
                  : r.status;
      return <span className={cls}>{label}</span>;
    }},
    { key: 'when', header: t('production.columns.completed'), render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
    { key: 'by', header: t('production.columns.by'), render: (r) => r.created_by_name ?? '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <button
        className="btn-ghost p-1.5 text-red-600"
        onClick={(e) => { e.stopPropagation(); setToDelete(r); }}
      >
        <Trash2 size={14} />
      </button>
    )},
  ];

  const exportColumns: ExportColumn<ProductionRun>[] = [
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

  return (
    <>
      <PageHeader
        title={t('production.title')}
        subtitle={t('production.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="production-runs"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated(
                (p) => production.runs.list(p),
                list.search ? { search: list.search } : {},
              )}
            />
            <button onClick={() => setOpen(true)} className="btn-primary">
              <PlayCircle size={16} /> {t('production.new')}
            </button>
          </>
        }
      />
      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('production.searchPlaceholder')} />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Factory} title={t('production.emptyTitle')} description={t('production.emptyDescription')} />}
        />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t('production.newTitle')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</button>
            <button
              className="btn-primary"
              disabled={!productId || !qty || execute.isPending}
              onClick={() => execute.mutate()}
            >
              {execute.isPending ? t('production.footer.recording') : t('production.footer.record')}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">{t('production.fields.product')}</label>
            <select className="input" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">{t('common.select')}</option>
              {products.data?.results.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t('production.fields.quantity')}</label>
              <input type="number" step="0.0001" className="input" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('production.fields.scheduledFor')}</label>
              <input type="date" className="input" value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">{t('production.fields.notesOptional')}</label>
            <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <p className="text-xs text-slate-500">
            {t('production.footer.hint')}
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('production.deleteTitle')}
        message={t('production.deleteMessage')}
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
