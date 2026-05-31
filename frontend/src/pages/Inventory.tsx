import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Boxes, AlertTriangle, History, Sliders, ChefHat } from 'lucide-react';
import { toast } from 'sonner';

import { inventory } from '@/api/endpoints';
import { processedMaterials } from '@/api/processed-materials';
import { extractErrorMessage } from '@/api/client';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { useCrudList } from '@/hooks/useCrudList';
import { formatNumber, formatDateTime } from '@/lib/format';
import type { StockItem, StockMovement } from '@/api/types';
import type { ProcessedMaterialStock } from '@/api/processed-materials';

type Tab = 'all' | 'low' | 'movements' | 'processed';

export function InventoryPage() {
  const [tab, setTab] = useState<Tab>('all');
  const [adjustOpen, setAdjustOpen] = useState<StockItem | null>(null);

  return (
    <>
      <PageHeader title="Inventory" subtitle="On-hand stock for products, raw materials, and processed materials" />

      <div className="card">
        <div className="card-header gap-2 flex-wrap">
          <div className="flex gap-1">
            {([
              { key: 'all', label: 'All stock', icon: Boxes },
              { key: 'low', label: 'Low stock', icon: AlertTriangle },
              { key: 'processed', label: 'Processed', icon: ChefHat },
              { key: 'movements', label: 'Movements', icon: History },
            ] as { key: Tab; label: string; icon: typeof Boxes }[]).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-1.5 ${
                  tab === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'all' && <AllStockTab onAdjust={setAdjustOpen} />}
        {tab === 'low' && <LowStockTab onAdjust={setAdjustOpen} />}
        {tab === 'processed' && <ProcessedStockTab />}
        {tab === 'movements' && <MovementsTab />}
      </div>

      <AdjustModal stock={adjustOpen} onClose={() => setAdjustOpen(null)} />
    </>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────
function StockColumns(onAdjust: (s: StockItem) => void): Column<StockItem>[] {
  return [
    { key: 'name', header: 'Item', render: (r) => (
      <div>
        <p className="font-medium">{r.item_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.item_sku}</p>
      </div>
    )},
    { key: 'kind', header: 'Type', render: (r) =>
      r.kind === 'product' ? <span className="badge-blue">Product</span> : <span className="badge-gray">Material</span>
    },
    { key: 'qty', header: 'On hand', align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatNumber(r.quantity, 2)} {r.item_unit}
      </span>
    )},
    { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
    { key: 'status', header: 'Status', render: (r) =>
      r.is_low ? <span className="badge-red">Low</span> : <span className="badge-green">OK</span>
    },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <button className="btn-secondary px-2 py-1 text-xs" onClick={() => onAdjust(r)}>
        <Sliders size={12} /> Adjust
      </button>
    )},
  ];
}

const stockExportColumns: ExportColumn<StockItem>[] = [
  { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
  { key: 'item_name', header: 'Item', value: (r) => r.item_name },
  { key: 'kind', header: 'Type', value: (r) => r.kind },
  { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
  { key: 'quantity', header: 'On hand', value: (r) => Number(r.quantity) },
  { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
  { key: 'is_low', header: 'Low stock', value: (r) => (r.is_low ? 'yes' : 'no') },
];

function AllStockTab({ onAdjust }: { onAdjust: (s: StockItem) => void }) {
  const list = useCrudList<StockItem>({
    queryKey: ['stock'],
    fetcher: (p) => inventory.stock.list(p),
  });
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search stock items…" />
        <ExportMenu
          filename="stock"
          columns={stockExportColumns}
          fetchRows={() => fetchAllPaginated(
            (p) => inventory.stock.list(p),
            list.search ? { search: list.search } : {},
          )}
        />
      </div>
      <DataTable
        columns={StockColumns(onAdjust)}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={Boxes} title="No stock yet" description="Stock entries appear as you create products and materials." />}
      />
      {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />}
    </>
  );
}

function LowStockTab({ onAdjust }: { onAdjust: (s: StockItem) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['stock-low'],
    queryFn: () => inventory.stock.low(),
  });
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-end">
        <ExportMenu
          filename="low-stock"
          columns={stockExportColumns}
          fetchRows={async () => (await inventory.stock.low()).results}
        />
      </div>
      <DataTable
        columns={StockColumns(onAdjust)}
        data={data?.results}
        loading={isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={AlertTriangle} title="No items below threshold" description="All stocks look healthy." />}
      />
    </>
  );
}

function MovementsTab() {
  const list = useCrudList<StockMovement>({
    queryKey: ['movements'],
    fetcher: (p) => inventory.movements.list(p),
  });
  const columns: Column<StockMovement>[] = [
    { key: 'when', header: 'When', render: (r) => formatDateTime(r.created_at) },
    { key: 'item', header: 'Item', render: (r) => <span className="font-medium">{r.item_name}</span> },
    { key: 'reason', header: 'Reason', render: (r) => <span className="badge-gray">{r.reason_display}</span> },
    { key: 'delta', header: 'Δ', align: 'right', render: (r) => (
      <span className={Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
        {Number(r.quantity_delta) > 0 ? '+' : ''}{formatNumber(r.quantity_delta, 2)} {r.item_unit}
      </span>
    )},
    { key: 'balance', header: 'After', align: 'right', render: (r) => `${formatNumber(r.balance_after, 2)} ${r.item_unit}` },
    { key: 'ref', header: 'Ref', render: (r) => <span className="font-mono text-xs">{r.reference || '—'}</span> },
    { key: 'who', header: 'By', render: (r) => r.created_by_name ?? '—' },
  ];
  const exportColumns: ExportColumn<StockMovement>[] = [
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
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-end">
        <ExportMenu
          filename="stock-movements"
          columns={exportColumns}
          fetchRows={() => fetchAllPaginated((p) => inventory.movements.list(p))}
        />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={History} title="No stock movements yet" />}
      />
      {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />}
    </>
  );
}

function AdjustModal({ stock, onClose }: { stock: StockItem | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [delta, setDelta] = useState('');
  const [note, setNote] = useState('');

  const mutate = useMutation({
    mutationFn: () => inventory.stock.adjust({
      product: stock?.kind === 'product' ? stock.product! : undefined,
      raw_material: stock?.kind === 'raw_material' ? stock.raw_material! : undefined,
      quantity_delta: Number(delta),
      note,
    }),
    onSuccess: () => {
      toast.success('Adjustment recorded.');
      qc.invalidateQueries({ queryKey: ['stock'] });
      qc.invalidateQueries({ queryKey: ['movements'] });
      qc.invalidateQueries({ queryKey: ['stock-low'] });
      onClose(); setDelta(''); setNote('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!stock) return null;

  return (
    <Modal
      open={!!stock}
      onClose={onClose}
      title={`Adjust: ${stock.item_name}`}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={!delta || Number(delta) === 0 || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending ? 'Saving…' : 'Apply'}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        Current on-hand: <strong>{formatNumber(stock.quantity, 2)} {stock.item_unit}</strong>.
        Enter a positive number to add stock, negative to remove (e.g. waste).
      </p>
      <div className="space-y-3">
        <div>
          <label className="label">Delta ({stock.item_unit})</label>
          <input
            type="number" step="0.01" className="input"
            value={delta} onChange={(e) => setDelta(e.target.value)} autoFocus
          />
        </div>
        <div>
          <label className="label">Note (optional)</label>
          <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Processed materials stock tab ─────────────────────────────────────────
function ProcessedStockTab() {
  const list = useCrudList<ProcessedMaterialStock>({
    queryKey: ['processed-stock'],
    fetcher: (p) => processedMaterials.stock.list(p),
  });
  const columns: Column<ProcessedMaterialStock>[] = [
    { key: 'name', header: 'Item', render: (r) => (
      <div>
        <p className="font-medium">{r.item_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.item_sku}</p>
      </div>
    )},
    { key: 'kind', header: 'Type', render: () => (
      <span className="badge-yellow">Processed</span>
    )},
    { key: 'qty', header: 'On hand', align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatNumber(r.quantity, 2)} {r.item_unit}
      </span>
    )},
    { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => (
      formatNumber(r.reorder_threshold, 2)
    )},
    { key: 'status', header: 'Status', render: (r) => (
      r.is_low ? <span className="badge-red">Low</span> : <span className="badge-green">OK</span>
    )},
  ];
  const exportColumns: ExportColumn<ProcessedMaterialStock>[] = [
    { key: 'item_sku', header: 'SKU', value: (r) => r.item_sku },
    { key: 'item_name', header: 'Item', value: (r) => r.item_name },
    { key: 'item_unit', header: 'Unit', value: (r) => r.item_unit },
    { key: 'quantity', header: 'On hand', value: (r) => Number(r.quantity) },
    { key: 'reorder_threshold', header: 'Reorder threshold', value: (r) => Number(r.reorder_threshold) },
    { key: 'is_low', header: 'Low stock', value: (r) => (r.is_low ? 'yes' : 'no') },
  ];
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search processed materials…" />
        <ExportMenu
          filename="processed-stock"
          columns={exportColumns}
          fetchRows={() => fetchAllPaginated(
            (p) => processedMaterials.stock.list(p),
            list.search ? { search: list.search } : {},
          )}
        />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState
          icon={ChefHat}
          title="No processed materials in stock"
          description='Manage processed materials under Catalog → Processed materials.'
        />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}
    </>
  );
}
