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
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('all');
  const [adjustOpen, setAdjustOpen] = useState<StockItem | null>(null);

  const tabs: { key: Tab; label: string; icon: typeof Boxes }[] = [
    { key: 'all', label: t('inventory.tabs.all'), icon: Boxes },
    { key: 'low', label: t('inventory.tabs.low'), icon: AlertTriangle },
    { key: 'processed', label: t('inventory.tabs.processed'), icon: ChefHat },
    { key: 'movements', label: t('inventory.tabs.movements'), icon: History },
  ];

  return (
    <>
      <PageHeader title={t('inventory.title')} subtitle={t('inventory.subtitle')} />

      <div className="card">
        <div className="card-header gap-2 flex-wrap">
          <div className="flex gap-1">
            {tabs.map(({ key, label, icon: Icon }) => (
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
function useStockColumns(onAdjust: (s: StockItem) => void): Column<StockItem>[] {
  const { t } = useTranslation();
  return [
    { key: 'name', header: t('inventory.columns.item'), render: (r) => (
      <div>
        <p className="font-medium">{r.item_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.item_sku}</p>
      </div>
    )},
    { key: 'kind', header: t('inventory.columns.type'), render: (r) =>
      r.kind === 'product'
        ? <span className="badge-blue">{t('inventory.badges.product')}</span>
        : <span className="badge-gray">{t('inventory.badges.material')}</span>
    },
    { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatNumber(r.quantity, 2)} {r.item_unit}
      </span>
    )},
    { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
    { key: 'status', header: t('inventory.columns.status'), render: (r) =>
      r.is_low
        ? <span className="badge-red">{t('inventory.badges.low')}</span>
        : <span className="badge-green">{t('inventory.badges.ok')}</span>
    },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <button className="btn-secondary px-2 py-1 text-xs" onClick={() => onAdjust(r)}>
        <Sliders size={12} /> {t('inventory.actions.adjust')}
      </button>
    )},
  ];
}

function useStockExportColumns(): ExportColumn<StockItem>[] {
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

function AllStockTab({ onAdjust }: { onAdjust: (s: StockItem) => void }) {
  const { t } = useTranslation();
  const list = useCrudList<StockItem>({
    queryKey: ['stock'],
    fetcher: (p) => inventory.stock.list(p),
  });
  const columns = useStockColumns(onAdjust);
  const exportColumns = useStockExportColumns();
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('inventory.search.all')} />
        <ExportMenu
          filename="stock"
          columns={exportColumns}
          fetchRows={() => fetchAllPaginated(
            (p) => inventory.stock.list(p),
            list.search ? { search: list.search } : {},
          )}
        />
      </div>
      <DataTable
        columns={columns}
        data={list.data?.results}
        loading={list.isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={Boxes} title={t('inventory.empty.stock')} description={t('inventory.empty.stockDescription')} />}
      />
      {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />}
    </>
  );
}

function LowStockTab({ onAdjust }: { onAdjust: (s: StockItem) => void }) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ['stock-low'],
    queryFn: () => inventory.stock.low(),
  });
  const columns = useStockColumns(onAdjust);
  const exportColumns = useStockExportColumns();
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-end">
        <ExportMenu
          filename="low-stock"
          columns={exportColumns}
          fetchRows={async () => (await inventory.stock.low()).results}
        />
      </div>
      <DataTable
        columns={columns}
        data={data?.results}
        loading={isLoading}
        rowKey={(r) => r.id}
        empty={<EmptyState icon={AlertTriangle} title={t('inventory.empty.low')} description={t('inventory.empty.lowDescription')} />}
      />
    </>
  );
}

function MovementsTab() {
  const { t } = useTranslation();
  const list = useCrudList<StockMovement>({
    queryKey: ['movements'],
    fetcher: (p) => inventory.movements.list(p),
  });
  const columns: Column<StockMovement>[] = [
    { key: 'when', header: t('inventory.columns.when'), render: (r) => formatDateTime(r.created_at) },
    { key: 'item', header: t('inventory.columns.item'), render: (r) => <span className="font-medium">{r.item_name}</span> },
    { key: 'reason', header: t('inventory.columns.reason'), render: (r) => <span className="badge-gray">{r.reason_display}</span> },
    { key: 'delta', header: t('inventory.columns.delta'), align: 'right', render: (r) => (
      <span className={Number(r.quantity_delta) >= 0 ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
        {Number(r.quantity_delta) > 0 ? '+' : ''}{formatNumber(r.quantity_delta, 2)} {r.item_unit}
      </span>
    )},
    { key: 'balance', header: t('inventory.columns.after'), align: 'right', render: (r) => `${formatNumber(r.balance_after, 2)} ${r.item_unit}` },
    { key: 'ref', header: t('inventory.columns.ref'), render: (r) => <span className="font-mono text-xs">{r.reference || '—'}</span> },
    { key: 'who', header: t('inventory.columns.by'), render: (r) => r.created_by_name ?? '—' },
  ];
  const exportColumns: ExportColumn<StockMovement>[] = [
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
        empty={<EmptyState icon={History} title={t('inventory.empty.movements')} />}
      />
      {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />}
    </>
  );
}

function AdjustModal({ stock, onClose }: { stock: StockItem | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
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
      toast.success(t('inventory.adjust.recorded'));
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
      title={t('inventory.adjust.title', { name: stock.item_name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!delta || Number(delta) === 0 || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending ? t('common.saving') : t('common.apply')}
          </button>
        </>
      }
    >
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('inventory.adjust.currentOnHand', {
            qty: formatNumber(stock.quantity, 2),
            unit: stock.item_unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">{t('inventory.adjust.delta', { unit: stock.item_unit })}</label>
          <input
            type="number" step="0.01" className="input"
            value={delta} onChange={(e) => setDelta(e.target.value)} autoFocus
          />
        </div>
        <div>
          <label className="label">{t('common.noteOptional')}</label>
          <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Processed materials stock tab ─────────────────────────────────────────
function ProcessedStockTab() {
  const { t } = useTranslation();
  const list = useCrudList<ProcessedMaterialStock>({
    queryKey: ['processed-stock'],
    fetcher: (p) => processedMaterials.stock.list(p),
  });
  const columns: Column<ProcessedMaterialStock>[] = [
    { key: 'name', header: t('inventory.columns.item'), render: (r) => (
      <div>
        <p className="font-medium">{r.item_name}</p>
        <p className="text-xs text-slate-500 font-mono">{r.item_sku}</p>
      </div>
    )},
    { key: 'kind', header: t('inventory.columns.type'), render: () => (
      <span className="badge-yellow">{t('inventory.badges.processed')}</span>
    )},
    { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatNumber(r.quantity, 2)} {r.item_unit}
      </span>
    )},
    { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => (
      formatNumber(r.reorder_threshold, 2)
    )},
    { key: 'status', header: t('inventory.columns.status'), render: (r) => (
      r.is_low
        ? <span className="badge-red">{t('inventory.badges.low')}</span>
        : <span className="badge-green">{t('inventory.badges.ok')}</span>
    )},
  ];
  const exportColumns: ExportColumn<ProcessedMaterialStock>[] = [
    { key: 'item_sku', header: t('inventory.exportCols.sku'), value: (r) => r.item_sku },
    { key: 'item_name', header: t('inventory.exportCols.item'), value: (r) => r.item_name },
    { key: 'item_unit', header: t('inventory.exportCols.unit'), value: (r) => r.item_unit },
    { key: 'quantity', header: t('inventory.exportCols.onHand'), value: (r) => Number(r.quantity) },
    { key: 'reorder_threshold', header: t('inventory.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
    { key: 'is_low', header: t('inventory.exportCols.lowStock'), value: (r) => (r.is_low ? t('common.yes') : t('common.no')) },
  ];
  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2">
        <SearchBar value={list.search} onChange={list.setSearch} placeholder={t('inventory.search.processed')} />
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
          title={t('inventory.empty.processed')}
          description={t('inventory.empty.processedDescription')}
        />}
      />
      {list.data && (
        <Pagination page={list.page} pageSize={list.pageSize} total={list.data.count} onChange={list.setPage} />
      )}
    </>
  );
}
