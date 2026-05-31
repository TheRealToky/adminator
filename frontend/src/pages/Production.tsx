import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Factory, PlayCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

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
import { formatDate, formatDateTime, formatMoney, formatNumber } from '@/lib/format';
import type { ProductionRun } from '@/api/types';

export function ProductionPage() {
  const qc = useQueryClient();
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
      toast.success('Production run recorded.');
      qc.invalidateQueries({ queryKey: ['production-runs'] });
      qc.invalidateQueries({ queryKey: ['stock'] });
      qc.invalidateQueries({ queryKey: ['movements'] });
      setOpen(false); setProductId(''); setQty(''); setNotes('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const columns: Column<ProductionRun>[] = [
    { key: 'sched', header: 'Scheduled', render: (r) => formatDate(r.scheduled_for) },
    { key: 'product', header: 'Product', render: (r) => (
      <div>
        <p className="font-medium">{r.product_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.product_sku}</p>
      </div>
    )},
    { key: 'qty', header: 'Quantity', align: 'right', render: (r) => formatNumber(r.quantity, 2) },
    { key: 'cost', header: 'Cost', align: 'right', render: (r) => formatMoney(r.cost) },
    { key: 'status', header: 'Status', render: (r) => {
      const cls = r.status === 'completed' ? 'badge-green'
                : r.status === 'planned' ? 'badge-blue'
                : 'badge-gray';
      return <span className={cls}>{r.status}</span>;
    }},
    { key: 'when', header: 'Completed', render: (r) => r.completed_at ? formatDateTime(r.completed_at) : '—' },
    { key: 'by', header: 'By', render: (r) => r.created_by_name ?? '—' },
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

  return (
    <>
      <PageHeader
        title="Production"
        subtitle="Bake & cook runs — automatically consumes raw materials"
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
              <PlayCircle size={16} /> New run
            </button>
          </>
        }
      />
      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search by product…" />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Factory} title="No production runs yet" description="Record what you bake to keep stock and costs accurate." />}
        />
        {list.data && (
          <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
        )}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New production run"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!productId || !qty || execute.isPending}
              onClick={() => execute.mutate()}
            >
              {execute.isPending ? 'Recording…' : 'Record'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">Product</label>
            <select className="input" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">— Select —</option>
              {products.data?.results.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Quantity</label>
              <input type="number" step="0.01" className="input" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div>
              <label className="label">Scheduled for</label>
              <input type="date" className="input" value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">Notes (optional)</label>
            <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <p className="text-xs text-slate-500">
            Recording a run will deduct each ingredient from raw material stock based on the product's recipe.
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title="Delete this run?"
        message="The run will be removed but related stock movements are preserved for audit."
        confirmLabel="Delete"
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (!toDelete) return;
          list.deleteMutation.mutate(toDelete.id, { onSettled: () => setToDelete(null) });
        }}
      />
    </>
  );
}
