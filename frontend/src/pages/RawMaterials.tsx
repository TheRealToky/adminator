import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Tag, PackagePlus } from 'lucide-react';
import { toast } from 'sonner';

import { catalog, inventory } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatMoney, formatNumber } from '@/lib/format';
import type { RawMaterial } from '@/api/types';

const empty: Partial<RawMaterial> = {
  sku: '', name: '', unit: 'g', unit_cost: '0', reorder_threshold: '0',
  preferred_supplier: null, is_active: true,
};

export function RawMaterialsPage() {
  const qc = useQueryClient();
  const list = useCrudList<RawMaterial>({
    queryKey: ['raw-materials'],
    fetcher: (p) => catalog.rawMaterials.list(p),
    deleter: (id) => catalog.rawMaterials.remove(id),
  });

  const units = useQuery({ queryKey: ['units'], queryFn: catalog.units });
  const suppliers = useQuery({ queryKey: ['suppliers-all'], queryFn: () => catalog.suppliers.list({ page_size: 200 }) });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<RawMaterial | null>(null);
  const [form, setForm] = useState<Partial<RawMaterial>>(empty);
  const [toDelete, setToDelete] = useState<RawMaterial | null>(null);
  const [receiveOpen, setReceiveOpen] = useState<RawMaterial | null>(null);
  const [receiveQty, setReceiveQty] = useState('');

  const save = useMutation({
    mutationFn: () =>
      editing ? catalog.rawMaterials.update(editing.id, form) : catalog.rawMaterials.create(form),
    onSuccess: () => {
      toast.success(editing ? 'Material updated.' : 'Material created.');
      qc.invalidateQueries({ queryKey: ['raw-materials'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const receive = useMutation({
    mutationFn: () =>
      inventory.stock.receive({
        raw_material: receiveOpen!.id,
        quantity: Number(receiveQty),
        reference: 'Purchase',
      }),
    onSuccess: () => {
      toast.success(`Received ${receiveQty} ${receiveOpen?.unit}.`);
      qc.invalidateQueries({ queryKey: ['stock'] });
      setReceiveOpen(null);
      setReceiveQty('');
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() { setEditing(null); setForm(empty); setOpen(true); }
  function openEdit(row: RawMaterial) { setEditing(row); setForm(row); setOpen(true); }

  const columns: Column<RawMaterial>[] = [
    { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
    { key: 'name', header: 'Name', render: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'unit', header: 'Unit', render: (r) => r.unit },
    { key: 'cost', header: 'Cost / unit', align: 'right', render: (r) => formatMoney(r.unit_cost) },
    { key: 'thresh', header: 'Reorder ≤', align: 'right', render: (r) => formatNumber(r.reorder_threshold, 2) },
    { key: 'supplier', header: 'Supplier', render: (r) => r.preferred_supplier_name ?? '—' },
    { key: 'actions', header: '', align: 'right', render: (r) => (
      <div className="flex justify-end gap-1">
        <button
          className="btn-ghost p-1.5 text-emerald-700"
          title="Receive stock"
          onClick={(e) => { e.stopPropagation(); setReceiveOpen(r); }}
        >
          <PackagePlus size={14} />
        </button>
        <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); openEdit(r); }}>
          <Pencil size={14} />
        </button>
        <button className="btn-ghost p-1.5 text-red-600" onClick={(e) => { e.stopPropagation(); setToDelete(r); }}>
          <Trash2 size={14} />
        </button>
      </div>
    )},
  ];

  return (
    <>
      <PageHeader
        title="Raw materials"
        subtitle="Ingredients & supplies consumed by production"
        actions={<button onClick={openCreate} className="btn-primary"><Plus size={16} /> New material</button>}
      />

      <div className="card">
        <div className="card-header">
          <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search by name or SKU…" />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={<EmptyState icon={Tag} title="No raw materials yet" description="Add ingredients used in production." />}
        />
        {list.data && (
          <Pagination
            page={list.page}
            pageSize={list.pageSize}
            total={list.data.count}
            onChange={list.setPage}
          />
        )}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? 'Edit raw material' : 'New raw material'}
        size="lg"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending || !form.name || !form.sku}>
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="label">SKU</label>
            <input className="input font-mono" value={form.sku ?? ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          </div>
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Unit</label>
            <select className="input" value={form.unit ?? 'g'} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              {units.data?.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Cost per unit</label>
            <input type="number" step="0.0001" className="input" value={form.unit_cost ?? '0'} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} />
          </div>
          <div>
            <label className="label">Reorder threshold</label>
            <input type="number" step="0.01" className="input" value={form.reorder_threshold ?? '0'} onChange={(e) => setForm({ ...form, reorder_threshold: e.target.value })} />
          </div>
          <div>
            <label className="label">Preferred supplier</label>
            <select
              className="input"
              value={form.preferred_supplier ?? ''}
              onChange={(e) => setForm({ ...form, preferred_supplier: e.target.value || null })}
            >
              <option value="">— None —</option>
              {suppliers.data?.results.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <input id="active-rm" type="checkbox" checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <label htmlFor="active-rm" className="text-sm">Active</label>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!receiveOpen}
        onClose={() => setReceiveOpen(null)}
        title={`Receive: ${receiveOpen?.name ?? ''}`}
        size="sm"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setReceiveOpen(null)}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!receiveQty || Number(receiveQty) <= 0 || receive.isPending}
              onClick={() => receive.mutate()}
            >
              {receive.isPending ? 'Recording…' : 'Record'}
            </button>
          </>
        }
      >
        <div>
          <label className="label">Quantity received ({receiveOpen?.unit})</label>
          <input
            autoFocus
            type="number" step="0.01"
            className="input"
            value={receiveQty}
            onChange={(e) => setReceiveQty(e.target.value)}
          />
          <p className="text-xs text-slate-500 mt-2">
            This logs a stock-in movement and updates current on-hand stock.
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title="Delete material?"
        message={`Delete "${toDelete?.name}"? Linked recipes will also be affected.`}
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
