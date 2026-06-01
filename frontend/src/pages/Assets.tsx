import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Building, PackageOpen, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { catalog, finance } from '@/api/endpoints';
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
import { formatDate, formatMoney } from '@/lib/format';
import type { Asset, AssetCategoryKey } from '@/api/types';

const CATEGORY_KEYS: AssetCategoryKey[] = [
  'equipment',
  'furniture',
  'vehicle',
  'electronics',
  'fit_out',
  'other',
];

type AssetFormState = Partial<Asset> & {
  record_as_expense?: boolean;
  expense_category?: string;
};

const emptyForm: AssetFormState = {
  name: '',
  category: 'equipment',
  purchase_date: new Date().toISOString().slice(0, 10),
  purchase_cost: '0',
  useful_life_months: null,
  supplier: null,
  reference: '',
  notes: '',
  record_as_expense: false,
  expense_category: '',
};

export function AssetsPage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const list = useCrudList<Asset>({
    queryKey: ['assets'],
    fetcher: (p) => finance.assets.list(p),
    deleter: (id) => finance.assets.remove(id),
  });

  const suppliers = useQuery({
    queryKey: ['suppliers-for-assets'],
    queryFn: () => catalog.suppliers.list({ page_size: 200, is_active: true }),
  });
  const expenseCategories = useQuery({
    queryKey: ['expense-cats-for-assets'],
    queryFn: () => finance.expenseCategories.list({ page_size: 200 }),
  });

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Asset | null>(null);
  const [form, setForm] = useState<AssetFormState>(emptyForm);
  const [toDelete, setToDelete] = useState<Asset | null>(null);

  const save = useMutation({
    mutationFn: () => {
      if (editing) {
        // Only send editable fields on update — strip the create-only auto-expense flags.
        const { record_as_expense: _r, expense_category: _e, ...patch } = form;
        return finance.assets.update(editing.id, patch);
      }
      return finance.assets.create(form);
    },
    onSuccess: () => {
      toast.success(editing ? t('assets.updated') : t('assets.created'));
      qc.invalidateQueries({ queryKey: ['assets'] });
      setOpen(false);
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const dispose = useMutation({
    mutationFn: (id: string) => finance.assets.dispose(id),
    onSuccess: () => {
      toast.success(t('assets.disposed'));
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  const reactivate = useMutation({
    mutationFn: (id: string) => finance.assets.reactivate(id),
    onSuccess: () => {
      toast.success(t('assets.reactivated'));
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
    onError: (e) => toast.error(extractErrorMessage(e)),
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  }

  function openEdit(row: Asset) {
    setEditing(row);
    setForm({
      name: row.name,
      category: row.category,
      purchase_date: row.purchase_date,
      purchase_cost: row.purchase_cost,
      useful_life_months: row.useful_life_months,
      supplier: row.supplier,
      reference: row.reference,
      notes: row.notes,
      status: row.status,
    });
    setOpen(true);
  }

  const columns: Column<Asset>[] = [
    {
      key: 'name',
      header: t('assets.columns.name'),
      render: (r) => (
        <div>
          <div className="font-medium">{r.name}</div>
          {r.reference && (
            <div className="text-xs text-slate-500">{r.reference}</div>
          )}
        </div>
      ),
    },
    {
      key: 'category',
      header: t('assets.columns.category'),
      render: (r) => t(`assets.categories.${r.category}`),
    },
    {
      key: 'purchase_date',
      header: t('assets.columns.purchased'),
      render: (r) => formatDate(r.purchase_date),
    },
    {
      key: 'purchase_cost',
      header: t('assets.columns.cost'),
      align: 'right',
      render: (r) => formatMoney(r.purchase_cost),
    },
    {
      key: 'life',
      header: t('assets.columns.usefulLife'),
      align: 'right',
      render: (r) =>
        r.useful_life_months
          ? t('assets.monthsValue', { count: r.useful_life_months })
          : '—',
    },
    {
      key: 'carrying',
      header: t('assets.columns.carryingValue'),
      align: 'right',
      render: (r) => (
        <span className="font-semibold">{formatMoney(r.carrying_value)}</span>
      ),
    },
    {
      key: 'status',
      header: t('assets.columns.status'),
      render: (r) =>
        r.status === 'active' ? (
          <span className="badge-green">
            {t('assets.statuses.active')}
          </span>
        ) : (
          <span className="badge-gray">
            {t('assets.statuses.disposed')}
          </span>
        ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <div className="flex justify-end gap-1">
          {r.status === 'active' ? (
            <button
              className="btn-ghost p-1.5"
              title={t('assets.actions.dispose')}
              onClick={(e) => {
                e.stopPropagation();
                dispose.mutate(r.id);
              }}
            >
              <PackageOpen size={14} />
            </button>
          ) : (
            <button
              className="btn-ghost p-1.5"
              title={t('assets.actions.reactivate')}
              onClick={(e) => {
                e.stopPropagation();
                reactivate.mutate(r.id);
              }}
            >
              <RotateCcw size={14} />
            </button>
          )}
          <button
            className="btn-ghost p-1.5"
            onClick={(e) => {
              e.stopPropagation();
              openEdit(r);
            }}
          >
            <Pencil size={14} />
          </button>
          <button
            className="btn-ghost p-1.5 text-red-600"
            onClick={(e) => {
              e.stopPropagation();
              setToDelete(r);
            }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  const exportColumns: ExportColumn<Asset>[] = [
    { key: 'name', header: t('assets.exportCols.name'), value: (r) => r.name },
    {
      key: 'category',
      header: t('assets.exportCols.category'),
      value: (r) => t(`assets.categories.${r.category}`),
    },
    {
      key: 'purchase_date',
      header: t('assets.exportCols.purchased'),
      value: (r) => r.purchase_date,
    },
    {
      key: 'purchase_cost',
      header: t('assets.exportCols.cost'),
      value: (r) => Number(r.purchase_cost),
    },
    {
      key: 'useful_life_months',
      header: t('assets.exportCols.usefulLifeMonths'),
      value: (r) => r.useful_life_months ?? '',
    },
    {
      key: 'accumulated_depreciation',
      header: t('assets.exportCols.accumulatedDepreciation'),
      value: (r) => Number(r.accumulated_depreciation),
    },
    {
      key: 'carrying_value',
      header: t('assets.exportCols.carryingValue'),
      value: (r) => Number(r.carrying_value),
    },
    {
      key: 'supplier',
      header: t('assets.exportCols.supplier'),
      value: (r) => r.supplier_name ?? '',
    },
    {
      key: 'reference',
      header: t('assets.exportCols.reference'),
      value: (r) => r.reference,
    },
    {
      key: 'status',
      header: t('assets.exportCols.status'),
      value: (r) => t(`assets.statuses.${r.status}`),
    },
    { key: 'notes', header: t('assets.exportCols.notes'), value: (r) => r.notes },
  ];

  return (
    <>
      <PageHeader
        title={t('assets.title')}
        subtitle={t('assets.subtitle')}
        actions={
          <>
            <ExportMenu
              filename="assets"
              columns={exportColumns}
              fetchRows={() => fetchAllPaginated((p) => finance.assets.list(p))}
            />
            <button onClick={openCreate} className="btn-primary">
              <Plus size={16} /> {t('assets.new')}
            </button>
          </>
        }
      />

      <div className="card">
        <div className="p-3 border-b border-slate-200">
          <SearchBar
            value={list.search}
            onChange={list.setSearch}
            placeholder={t('assets.searchPlaceholder')}
          />
        </div>
        <DataTable
          columns={columns}
          data={list.data?.results}
          loading={list.isLoading}
          rowKey={(r) => r.id}
          empty={
            <EmptyState
              icon={Building}
              title={t('assets.emptyTitle')}
              description={t('assets.emptyDescription')}
            />
          }
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
        title={editing ? t('assets.editModal') : t('assets.newModal')}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </button>
            <button
              className="btn-primary"
              disabled={
                !form.name ||
                !form.purchase_cost ||
                Number(form.purchase_cost) <= 0 ||
                save.isPending
              }
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.saving') : t('common.save')}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="label">{t('assets.fields.name')}</label>
            <input
              className="input"
              value={form.name ?? ''}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('assets.fields.namePlaceholder')}
            />
          </div>

          <div>
            <label className="label">{t('assets.fields.category')}</label>
            <select
              className="input"
              value={form.category ?? 'equipment'}
              onChange={(e) =>
                setForm({ ...form, category: e.target.value as AssetCategoryKey })
              }
            >
              {CATEGORY_KEYS.map((k) => (
                <option key={k} value={k}>
                  {t(`assets.categories.${k}`)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="label">{t('assets.fields.purchaseDate')}</label>
            <input
              type="date"
              className="input"
              value={form.purchase_date ?? ''}
              onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
            />
          </div>

          <div>
            <label className="label">{t('assets.fields.purchaseCost')}</label>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input"
              value={form.purchase_cost ?? '0'}
              onChange={(e) => setForm({ ...form, purchase_cost: e.target.value })}
            />
          </div>

          <div>
            <label className="label">
              {t('assets.fields.usefulLifeMonths')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <input
              type="number"
              min="0"
              step="1"
              className="input"
              value={form.useful_life_months ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  useful_life_months: e.target.value === '' ? null : Number(e.target.value),
                })
              }
              placeholder={t('assets.fields.usefulLifePlaceholder')}
            />
          </div>

          <div>
            <label className="label">
              {t('assets.fields.supplier')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <select
              className="input"
              value={form.supplier ?? ''}
              onChange={(e) =>
                setForm({ ...form, supplier: e.target.value || null })
              }
            >
              <option value="">{t('common.none')}</option>
              {suppliers.data?.results.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="label">
              {t('assets.fields.reference')}{' '}
              <span className="text-slate-400">({t('common.optional')})</span>
            </label>
            <input
              className="input"
              value={form.reference ?? ''}
              onChange={(e) => setForm({ ...form, reference: e.target.value })}
              placeholder={t('assets.fields.referencePlaceholder')}
            />
          </div>

          <div className="sm:col-span-2">
            <label className="label">{t('common.notes')}</label>
            <textarea
              className="input"
              rows={2}
              value={form.notes ?? ''}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>

          {!editing && (
            <div className="sm:col-span-2 border-t border-slate-200 pt-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={!!form.record_as_expense}
                  onChange={(e) =>
                    setForm({ ...form, record_as_expense: e.target.checked })
                  }
                />
                {t('assets.fields.recordAsExpense')}
              </label>
              <p className="text-xs text-slate-500 mt-1">
                {t('assets.fields.recordAsExpenseHint')}
              </p>
              {form.record_as_expense && (
                <div className="mt-2">
                  <label className="label">
                    {t('assets.fields.expenseCategory')}
                  </label>
                  <select
                    className="input"
                    value={form.expense_category ?? ''}
                    onChange={(e) =>
                      setForm({ ...form, expense_category: e.target.value })
                    }
                  >
                    <option value="">{t('common.select')}</option>
                    {expenseCategories.data?.results.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('assets.deleteTitle')}
        message={t('assets.deleteMessage', { name: toDelete?.name ?? '' })}
        confirmLabel={t('common.delete')}
        loading={list.deleteMutation.isPending}
        onConfirm={() => {
          if (toDelete)
            list.deleteMutation.mutate(toDelete.id, {
              onSettled: () => setToDelete(null),
            });
        }}
      />
    </>
  );
}
