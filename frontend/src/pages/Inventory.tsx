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
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import { useCrudList } from '@/hooks/useCrudList';
import { formatQuantity, formatMoney, formatDateTime } from '@/lib/format';
import type { StockItem, StockMovement } from '@/api/types';
import type { ProcessedMaterialStock } from '@/api/processed-materials';

type Tab = 'all' | 'low' | 'movements';

/**
 * A single on-hand row across every inventory source. Products and raw
 * materials come from `inventory.stock` (already carrying `kind`); processed
 * materials are tagged with `kind: 'processed'` so the three load together.
 */
type UnifiedStock = StockItem | (ProcessedMaterialStock & { kind: 'processed' });

/** Type filter for the combined stock list. `all` shows every kind. */
type KindFilter = 'all' | 'product' | 'raw_material' | 'processed';

export function InventoryPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('all');
  const [adjustOpen, setAdjustOpen] = useState<StockItem | null>(null);
  const [pmAdjustOpen, setPmAdjustOpen] = useState<ProcessedMaterialStock | null>(null);
  const [writeOffOpen, setWriteOffOpen] = useState<StockItem | null>(null);
  const [pmWriteOffOpen, setPmWriteOffOpen] = useState<ProcessedMaterialStock | null>(null);

  const tabs: { key: Tab; label: string; icon: typeof Boxes }[] = [
    { key: 'all', label: t('inventory.tabs.all'), icon: Boxes },
    { key: 'low', label: t('inventory.tabs.low'), icon: AlertTriangle },
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

        {tab === 'all' && (
          <CombinedStockTab
            onAdjust={setAdjustOpen}
            onPmAdjust={setPmAdjustOpen}
            onWriteOff={setWriteOffOpen}
            onPmWriteOff={setPmWriteOffOpen}
          />
        )}
        {tab === 'low' && (
          <CombinedStockTab
            lowOnly
            onAdjust={setAdjustOpen}
            onPmAdjust={setPmAdjustOpen}
            onWriteOff={setWriteOffOpen}
            onPmWriteOff={setPmWriteOffOpen}
          />
        )}
        {tab === 'movements' && <MovementsTab />}
      </div>

      <AdjustModal stock={adjustOpen} onClose={() => setAdjustOpen(null)} />
      <ProcessedAdjustModal
        stock={pmAdjustOpen}
        onClose={() => setPmAdjustOpen(null)}
      />
      <WriteOffModal stock={writeOffOpen} onClose={() => setWriteOffOpen(null)} />
      <ProcessedWriteOffModal
        stock={pmWriteOffOpen}
        onClose={() => setPmWriteOffOpen(null)}
      />
    </>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────
const PAGE_SIZE = 25;

function tagProcessed(
  rows: ProcessedMaterialStock[],
): (ProcessedMaterialStock & { kind: 'processed' })[] {
  return rows.map((r) => ({ ...r, kind: 'processed' as const }));
}

/** Fetch products, raw materials, and processed materials and merge them. */
async function fetchCombinedStock(lowOnly: boolean): Promise<UnifiedStock[]> {
  const [stock, processed] = await Promise.all([
    lowOnly
      ? inventory.stock.low().then((r) => r.results)
      : fetchAllPaginated((p) => inventory.stock.list(p)),
    lowOnly
      ? processedMaterials.stock.low().then((r) => r.results)
      : fetchAllPaginated((p) => processedMaterials.stock.list(p)),
  ]);
  const rows: UnifiedStock[] = [...stock, ...tagProcessed(processed)];
  rows.sort((a, b) => a.item_name.localeCompare(b.item_name));
  return rows;
}

function useStockColumns(
  onAdjust: (s: StockItem) => void,
  onPmAdjust: (s: ProcessedMaterialStock) => void,
  onWriteOff: (s: StockItem) => void,
  onPmWriteOff: (s: ProcessedMaterialStock) => void,
): Column<UnifiedStock>[] {
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
        : r.kind === 'processed'
          ? <span className="badge-yellow">{t('inventory.badges.processed')}</span>
          : <span className="badge-gray">{t('inventory.badges.material')}</span>
    },
    { key: 'qty', header: t('inventory.columns.onHand'), align: 'right', render: (r) => (
      <span className={r.is_low ? 'text-red-600 font-semibold' : 'font-medium'}>
        {formatQuantity(r.quantity)} {r.item_unit}
      </span>
    )},
    { key: 'thresh', header: t('inventory.columns.reorder'), align: 'right', render: (r) => formatQuantity(r.reorder_threshold) },
    { key: 'status', header: t('inventory.columns.status'), render: (r) =>
      r.is_low
        ? <span className="badge-red">{t('inventory.badges.low')}</span>
        : <span className="badge-green">{t('inventory.badges.ok')}</span>
    },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-secondary px-2 py-1 text-xs"
          onClick={() => (r.kind === 'processed' ? onPmAdjust(r) : onAdjust(r))}
        >
          <Sliders size={12} /> {t('inventory.actions.adjust')}
        </button>
        <button
          className="btn-ghost px-2 py-1 text-xs text-red-600"
          title={t('inventory.actions.writeOff')}
          disabled={Number(r.quantity) <= 0}
          onClick={() => (r.kind === 'processed' ? onPmWriteOff(r) : onWriteOff(r))}
        >
          <Trash2 size={12} /> {t('inventory.actions.writeOff')}
        </button>
      </div>
    )},
  ];
}

function useStockExportColumns(): ExportColumn<UnifiedStock>[] {
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

function CombinedStockTab({
  lowOnly = false,
  onAdjust,
  onPmAdjust,
  onWriteOff,
  onPmWriteOff,
}: {
  lowOnly?: boolean;
  onAdjust: (s: StockItem) => void;
  onPmAdjust: (s: ProcessedMaterialStock) => void;
  onWriteOff: (s: StockItem) => void;
  onPmWriteOff: (s: ProcessedMaterialStock) => void;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState<KindFilter>('all');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: lowOnly ? ['stock-combined', 'low'] : ['stock-combined', 'all'],
    queryFn: () => fetchCombinedStock(lowOnly),
  });

  const columns = useStockColumns(onAdjust, onPmAdjust, onWriteOff, onPmWriteOff);
  const exportColumns = useStockExportColumns();

  const kindFilters: { key: KindFilter; label: string }[] = [
    { key: 'all', label: t('inventory.filter.all') },
    { key: 'product', label: t('inventory.filter.products') },
    { key: 'raw_material', label: t('inventory.filter.materials') },
    { key: 'processed', label: t('inventory.filter.processed') },
  ];

  const filtered = useMemo(() => {
    let rows = data ?? [];
    if (kind !== 'all') rows = rows.filter((r) => r.kind === kind);
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) => r.item_name.toLowerCase().includes(q) || r.item_sku.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, search, kind]);

  const pageRows = useMemo(
    () => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filtered, page],
  );

  const empty = lowOnly
    ? <EmptyState icon={AlertTriangle} title={t('inventory.empty.low')} description={t('inventory.empty.lowDescription')} />
    : <EmptyState icon={Boxes} title={t('inventory.empty.stock')} description={t('inventory.empty.stockDescription')} />;

  return (
    <>
      <div className="px-5 pt-3 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <SearchBar
            value={search}
            onChange={(v) => { setSearch(v); setPage(1); }}
            placeholder={t('inventory.search.all')}
          />
          <div className="flex gap-1">
            {kindFilters.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => { setKind(key); setPage(1); }}
                className={`px-2.5 py-1 rounded-md text-xs font-medium ${
                  kind === key ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <ExportMenu
          filename={lowOnly ? 'low-stock' : 'stock'}
          columns={exportColumns}
          fetchRows={async () => filtered}
        />
      </div>
      <DataTable
        columns={columns}
        data={isLoading ? undefined : pageRows}
        loading={isLoading}
        rowKey={(r) => `${r.kind}-${r.id}`}
        empty={empty}
      />
      {filtered.length > 0 && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={filtered.length} onChange={setPage} />
      )}
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
        {Number(r.quantity_delta) > 0 ? '+' : ''}{formatQuantity(r.quantity_delta)} {r.item_unit}
      </span>
    )},
    { key: 'balance', header: t('inventory.columns.after'), align: 'right', render: (r) => `${formatQuantity(r.balance_after)} ${r.item_unit}` },
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
      qc.invalidateQueries({ queryKey: ['stock-combined'] });
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
            qty: formatQuantity(stock.quantity),
            unit: stock.item_unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">{t('inventory.adjust.delta', { unit: stock.item_unit })}</label>
          <input
            type="number" step="0.0001" className="input"
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

// ── Adjust modal (processed materials) ───────────────────────────────────
function ProcessedAdjustModal({
  stock, onClose,
}: { stock: ProcessedMaterialStock | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [delta, setDelta] = useState('');
  const [note, setNote] = useState('');

  const mutate = useMutation({
    mutationFn: () => processedMaterials.stock.adjust({
      processed_material: stock!.processed_material,
      quantity_delta: Number(delta),
      note,
    }),
    onSuccess: () => {
      toast.success(t('processedMaterials.adjust.recorded'));
      qc.invalidateQueries({ queryKey: ['processed-stock'] });
      qc.invalidateQueries({ queryKey: ['stock-combined'] });
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      qc.invalidateQueries({ queryKey: ['processed-movements'] });
      onClose(); setDelta(''); setNote('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!stock) return null;

  return (
    <Modal
      open={!!stock}
      onClose={onClose}
      title={t('processedMaterials.adjust.title', { name: stock.item_name })}
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
          __html: t('processedMaterials.adjust.currentOnHand', {
            qty: formatQuantity(stock.quantity),
            unit: stock.item_unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">{t('processedMaterials.adjust.delta', { unit: stock.item_unit })}</label>
          <input
            type="number" step="0.0001" className="input"
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

// ── Write-off modal (products / raw materials) ───────────────────────────
function WriteOffModal({ stock, onClose }: { stock: StockItem | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [quantity, setQuantity] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');

  const mutate = useMutation({
    mutationFn: () => inventory.stock.writeOff({
      product: stock?.kind === 'product' ? stock.product! : undefined,
      raw_material: stock?.kind === 'raw_material' ? stock.raw_material! : undefined,
      quantity: Number(quantity),
      note,
      reference,
    }),
    onSuccess: () => {
      const qty = Number(quantity);
      const expense = qty * Number(stock?.item_unit_cost ?? 0);
      toast.success(
        expense > 0
          ? t('inventory.writeOff.recorded', {
              qty: formatQuantity(qty),
              unit: stock?.item_unit ?? '',
              name: stock?.item_name ?? '',
            })
          : t('inventory.writeOff.recordedNoCost', {
              qty: formatQuantity(qty),
              unit: stock?.item_unit ?? '',
              name: stock?.item_name ?? '',
            }),
      );
      qc.invalidateQueries({ queryKey: ['stock'] });
      qc.invalidateQueries({ queryKey: ['stock-combined'] });
      qc.invalidateQueries({ queryKey: ['stock-low'] });
      qc.invalidateQueries({ queryKey: ['movements'] });
      qc.invalidateQueries({ queryKey: ['expenses'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
      setQuantity(''); setNote(''); setReference('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!stock) return null;
  const onHand = Number(stock.quantity);
  const unitCost = Number(stock.item_unit_cost || 0);
  const qty = Number(quantity) || 0;
  const exceedsStock = qty > onHand;
  const expense = qty * unitCost;

  return (
    <Modal
      open={!!stock}
      onClose={onClose}
      title={t('inventory.writeOff.title', { name: stock.item_name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!quantity || qty <= 0 || exceedsStock || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending ? t('inventory.writeOff.submitting') : t('inventory.writeOff.submit')}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        {unitCost > 0 ? (
          <Trans
            i18nKey="inventory.writeOff.lead"
            values={{ cost: formatMoney(unitCost), unit: stock.item_unit }}
            components={{ 1: <strong /> }}
          />
        ) : (
          t('inventory.writeOff.leadZeroCost')
        )}
      </p>
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('inventory.writeOff.currentOnHand', {
            qty: formatQuantity(onHand),
            unit: stock.item_unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">
            {t('inventory.writeOff.quantity', { unit: stock.item_unit })}
          </label>
          <input
            autoFocus type="number" step="0.0001" min="0" max={onHand}
            className="input"
            value={quantity} onChange={(e) => setQuantity(e.target.value)}
          />
          {exceedsStock && (
            <p className="text-xs text-red-600 mt-1">
              {t('inventory.writeOff.exceedsOnHand', {
                qty: formatQuantity(onHand),
                unit: stock.item_unit,
              })}
            </p>
          )}
        </div>
        <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 flex items-center justify-between">
          <span className="text-xs text-slate-600">{t('inventory.writeOff.expenseToBook')}</span>
          <span className="text-sm font-semibold tabular-nums">
            {formatMoney(expense)}
          </span>
        </div>
        <div>
          <label className="label">{t('inventory.writeOff.reason')}</label>
          <textarea
            className="input" rows={2}
            placeholder={t('inventory.writeOff.reasonPlaceholder')}
            value={note} onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <div>
          <label className="label">{t('inventory.writeOff.reference')}</label>
          <input className="input" value={reference} onChange={(e) => setReference(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// ── Write-off modal (processed materials) ────────────────────────────────
function ProcessedWriteOffModal({
  stock, onClose,
}: { stock: ProcessedMaterialStock | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [quantity, setQuantity] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');

  const mutate = useMutation({
    mutationFn: () => processedMaterials.stock.writeOff({
      processed_material: stock!.processed_material,
      quantity: Number(quantity),
      note,
      reference,
    }),
    onSuccess: () => {
      const qty = Number(quantity);
      const expense = qty * Number(stock?.item_unit_cost ?? 0);
      toast.success(
        expense > 0
          ? t('processedMaterials.writeOff.recorded', {
              qty: formatQuantity(qty),
              unit: stock?.item_unit ?? '',
              name: stock?.item_name ?? '',
            })
          : t('processedMaterials.writeOff.recordedNoCost', {
              qty: formatQuantity(qty),
              unit: stock?.item_unit ?? '',
              name: stock?.item_name ?? '',
            }),
      );
      qc.invalidateQueries({ queryKey: ['processed-stock'] });
      qc.invalidateQueries({ queryKey: ['stock-combined'] });
      qc.invalidateQueries({ queryKey: ['processed-materials'] });
      qc.invalidateQueries({ queryKey: ['processed-movements'] });
      qc.invalidateQueries({ queryKey: ['expenses'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
      setQuantity(''); setNote(''); setReference('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  if (!stock) return null;
  const onHand = Number(stock.quantity);
  const unitCost = Number(stock.item_unit_cost || 0);
  const qty = Number(quantity) || 0;
  const exceedsStock = qty > onHand;
  const expense = qty * unitCost;

  return (
    <Modal
      open={!!stock}
      onClose={onClose}
      title={t('processedMaterials.writeOff.title', { name: stock.item_name })}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!quantity || qty <= 0 || exceedsStock || mutate.isPending}
            onClick={() => mutate.mutate()}
          >
            {mutate.isPending
              ? t('processedMaterials.writeOff.submitting')
              : t('processedMaterials.writeOff.submit')}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-500 mb-3">
        {unitCost > 0 ? (
          <Trans
            i18nKey="processedMaterials.writeOff.lead"
            values={{ cost: formatMoney(unitCost), unit: stock.item_unit }}
            components={{ 1: <strong /> }}
          />
        ) : (
          t('processedMaterials.writeOff.leadZeroCost')
        )}
      </p>
      <p
        className="text-sm text-slate-500 mb-3"
        dangerouslySetInnerHTML={{
          __html: t('processedMaterials.writeOff.currentOnHand', {
            qty: formatQuantity(onHand),
            unit: stock.item_unit,
          }),
        }}
      />
      <div className="space-y-3">
        <div>
          <label className="label">
            {t('processedMaterials.writeOff.quantity', { unit: stock.item_unit })}
          </label>
          <input
            autoFocus type="number" step="0.0001" min="0" max={onHand}
            className="input"
            value={quantity} onChange={(e) => setQuantity(e.target.value)}
          />
          {exceedsStock && (
            <p className="text-xs text-red-600 mt-1">
              {t('processedMaterials.writeOff.exceedsOnHand', {
                qty: formatQuantity(onHand),
                unit: stock.item_unit,
              })}
            </p>
          )}
        </div>
        <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 flex items-center justify-between">
          <span className="text-xs text-slate-600">{t('processedMaterials.writeOff.expenseToBook')}</span>
          <span className="text-sm font-semibold tabular-nums">
            {formatMoney(expense)}
          </span>
        </div>
        <div>
          <label className="label">{t('processedMaterials.writeOff.reason')}</label>
          <textarea
            className="input" rows={2}
            placeholder={t('processedMaterials.writeOff.reasonPlaceholder')}
            value={note} onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <div>
          <label className="label">{t('processedMaterials.writeOff.reference')}</label>
          <input className="input" value={reference} onChange={(e) => setReference(e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}
