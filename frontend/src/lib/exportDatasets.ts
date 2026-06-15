/**
 * Central registry of every table the app can export, used by the global
 * "Export all" action. Each dataset reuses the same columns and translation
 * keys as that table's own page-level ExportMenu, so a bundled export matches
 * what you'd get exporting each page individually.
 */
import { catalog, finance, inventory, production, sales, users } from '@/api/endpoints';
import {
  processedMaterials,
  type ProcessedMaterial,
  type ProcessedMaterialBatch,
  type ProcessedMaterialStockMovement,
} from '@/api/processed-materials';
import { fetchAllPaginated, type ExportColumn } from '@/lib/export';
import type {
  Asset, Budget, Invoice, ProductionRun, Product, RawMaterial, Sale, StockItem,
  StockMovement, Supplier, Transaction, TransactionCategory, User, Wallet,
} from '@/api/types';

/** Minimal translate signature — avoids coupling to a specific i18next type version. */
type Translate = (key: string, options?: Record<string, unknown>) => string;

export interface ExportDataset {
  key: string;
  /** Worksheet tab name (xlsx) and section label (csv/json). */
  title: string;
  columns: ExportColumn<unknown>[];
  fetchRows: () => Promise<unknown[]>;
}

/** Type-erase a strongly-typed dataset so the registry can hold them uniformly. */
function dataset<T>(d: {
  key: string;
  title: string;
  columns: ExportColumn<T>[];
  fetchRows: () => Promise<T[]>;
}): ExportDataset {
  return {
    key: d.key,
    title: d.title,
    columns: d.columns as unknown as ExportColumn<unknown>[],
    fetchRows: d.fetchRows as () => Promise<unknown[]>,
  };
}

export interface BuildDatasetsOptions {
  /** Include the staff table — the users endpoint is admin-only. */
  includeUsers?: boolean;
}

export function buildExportDatasets(
  t: Translate,
  { includeUsers = false }: BuildDatasetsOptions = {},
): ExportDataset[] {
  const yesNo = (v: boolean) => (v ? t('common.yes') : t('common.no'));
  const tbl = (key: string) => t(`export.all.tables.${key}`);

  const datasets: ExportDataset[] = [
    dataset<Product>({
      key: 'products',
      title: tbl('products'),
      fetchRows: () => fetchAllPaginated((p) => catalog.products.list(p)),
      columns: [
        { key: 'sku', header: t('products.exportCols.sku'), value: (r) => r.sku },
        { key: 'name', header: t('products.exportCols.name'), value: (r) => r.name },
        { key: 'category', header: t('products.exportCols.category'), value: (r) => r.category_name ?? '' },
        { key: 'unit', header: t('products.exportCols.unit'), value: (r) => r.unit },
        { key: 'selling_price', header: t('products.exportCols.sellingPrice'), value: (r) => Number(r.selling_price) },
        { key: 'production_cost', header: t('products.exportCols.productionCost'), value: (r) => Number(r.production_cost) },
        { key: 'margin', header: t('products.exportCols.margin'), value: (r) => Number(r.margin ?? 0) },
        { key: 'overhead_pct', header: t('products.exportCols.overheadPct'), value: (r) => Number(r.overhead_pct ?? 0) },
        { key: 'reorder_threshold', header: t('products.exportCols.reorderThreshold'), value: (r) => r.reorder_threshold },
        { key: 'is_active', header: t('products.exportCols.active'), value: (r) => yesNo(r.is_active) },
        { key: 'description', header: t('products.exportCols.description'), value: (r) => r.description },
      ],
    }),

    dataset<RawMaterial>({
      key: 'raw_materials',
      title: tbl('raw_materials'),
      fetchRows: () => fetchAllPaginated((p) => catalog.rawMaterials.list(p)),
      columns: [
        { key: 'sku', header: t('rawMaterials.exportCols.sku'), value: (r) => r.sku },
        { key: 'name', header: t('rawMaterials.exportCols.name'), value: (r) => r.name },
        { key: 'unit', header: t('rawMaterials.exportCols.unit'), value: (r) => r.unit },
        { key: 'unit_cost', header: t('rawMaterials.exportCols.unitCost'), value: (r) => Number(r.unit_cost) },
        { key: 'reorder_threshold', header: t('rawMaterials.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'preferred_supplier', header: t('rawMaterials.exportCols.preferredSupplier'), value: (r) => r.preferred_supplier_name ?? '' },
        { key: 'is_active', header: t('rawMaterials.exportCols.active'), value: (r) => yesNo(r.is_active) },
      ],
    }),

    dataset<ProcessedMaterial>({
      key: 'processed_materials',
      title: tbl('processed_materials'),
      fetchRows: () => fetchAllPaginated((p) => processedMaterials.list(p)),
      columns: [
        { key: 'sku', header: t('processedMaterials.exportCols.sku'), value: (r) => r.sku },
        { key: 'name', header: t('processedMaterials.exportCols.name'), value: (r) => r.name },
        { key: 'unit', header: t('processedMaterials.exportCols.unit'), value: (r) => r.unit },
        { key: 'yield_per_batch', header: t('processedMaterials.exportCols.yieldPerBatch'), value: (r) => Number(r.yield_per_batch) },
        { key: 'unit_cost', header: t('processedMaterials.exportCols.unitCost'), value: (r) => Number(r.unit_cost) },
        { key: 'overhead_pct', header: t('processedMaterials.exportCols.overheadPct'), value: (r) => Number(r.overhead_pct) },
        { key: 'shelf_life_hours', header: t('processedMaterials.exportCols.shelfLifeHours'), value: (r) => r.shelf_life_hours },
        { key: 'reorder_threshold', header: t('processedMaterials.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'stock_quantity', header: t('processedMaterials.exportCols.onHand'), value: (r) => Number(r.stock_quantity) },
        { key: 'is_low', header: t('processedMaterials.exportCols.lowStock'), value: (r) => yesNo(r.is_low) },
        { key: 'is_active', header: t('processedMaterials.exportCols.active'), value: (r) => yesNo(r.is_active) },
        { key: 'notes', header: t('processedMaterials.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<Supplier>({
      key: 'suppliers',
      title: tbl('suppliers'),
      fetchRows: () => fetchAllPaginated((p) => catalog.suppliers.list(p)),
      columns: [
        { key: 'name', header: t('suppliers.exportCols.name'), value: (r) => r.name },
        { key: 'contact_name', header: t('suppliers.exportCols.contact'), value: (r) => r.contact_name },
        { key: 'phone', header: t('suppliers.exportCols.phone'), value: (r) => r.phone },
        { key: 'email', header: t('suppliers.exportCols.email'), value: (r) => r.email },
        { key: 'address', header: t('suppliers.exportCols.address'), value: (r) => r.address },
        { key: 'notes', header: t('suppliers.exportCols.notes'), value: (r) => r.notes },
        { key: 'is_active', header: t('suppliers.exportCols.active'), value: (r) => yesNo(r.is_active) },
      ],
    }),

    dataset<StockItem>({
      key: 'stock',
      title: tbl('stock'),
      fetchRows: () => fetchAllPaginated((p) => inventory.stock.list(p)),
      columns: [
        { key: 'item_sku', header: t('inventory.exportCols.sku'), value: (r) => r.item_sku },
        { key: 'item_name', header: t('inventory.exportCols.item'), value: (r) => r.item_name },
        { key: 'kind', header: t('inventory.exportCols.type'), value: (r) => r.kind },
        { key: 'item_unit', header: t('inventory.exportCols.unit'), value: (r) => r.item_unit },
        { key: 'quantity', header: t('inventory.exportCols.onHand'), value: (r) => Number(r.quantity) },
        { key: 'reorder_threshold', header: t('inventory.exportCols.reorderThreshold'), value: (r) => Number(r.reorder_threshold) },
        { key: 'is_low', header: t('inventory.exportCols.lowStock'), value: (r) => yesNo(r.is_low) },
      ],
    }),

    dataset<StockMovement>({
      key: 'stock_movements',
      title: tbl('stock_movements'),
      fetchRows: () => fetchAllPaginated((p) => inventory.movements.list(p)),
      columns: [
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
      ],
    }),

    dataset<ProcessedMaterialStockMovement>({
      key: 'processed_material_movements',
      title: tbl('processed_material_movements'),
      fetchRows: () => fetchAllPaginated((p) => processedMaterials.movements.list(p)),
      columns: [
        { key: 'created_at', header: t('processedMaterials.movements.exportCols.when'), value: (r) => r.created_at },
        { key: 'item_sku', header: t('processedMaterials.movements.exportCols.sku'), value: (r) => r.item_sku },
        { key: 'item_name', header: t('processedMaterials.movements.exportCols.material'), value: (r) => r.item_name },
        { key: 'item_unit', header: t('processedMaterials.movements.exportCols.unit'), value: (r) => r.item_unit },
        { key: 'reason', header: t('processedMaterials.movements.exportCols.reason'), value: (r) => r.reason_display },
        { key: 'quantity_delta', header: t('processedMaterials.movements.exportCols.quantityDelta'), value: (r) => Number(r.quantity_delta) },
        { key: 'balance_after', header: t('processedMaterials.movements.exportCols.balanceAfter'), value: (r) => Number(r.balance_after) },
        { key: 'reference', header: t('processedMaterials.movements.exportCols.reference'), value: (r) => r.reference },
        { key: 'note', header: t('processedMaterials.movements.exportCols.note'), value: (r) => r.note },
        { key: 'created_by', header: t('processedMaterials.movements.exportCols.by'), value: (r) => r.created_by_name ?? '' },
      ],
    }),

    dataset<ProductionRun>({
      key: 'production_runs',
      title: tbl('production_runs'),
      fetchRows: () => fetchAllPaginated((p) => production.runs.list(p)),
      columns: [
        { key: 'scheduled_for', header: t('production.exportCols.scheduled'), value: (r) => r.scheduled_for },
        { key: 'completed_at', header: t('production.exportCols.completed'), value: (r) => r.completed_at ?? '' },
        { key: 'product_sku', header: t('production.exportCols.productSku'), value: (r) => r.product_sku },
        { key: 'product_name', header: t('production.exportCols.product'), value: (r) => r.product_name },
        { key: 'quantity', header: t('production.exportCols.quantity'), value: (r) => Number(r.quantity) },
        { key: 'cost', header: t('production.exportCols.cost'), value: (r) => Number(r.cost) },
        { key: 'status', header: t('production.exportCols.status'), value: (r) => r.status },
        { key: 'created_by', header: t('production.exportCols.by'), value: (r) => r.created_by_name ?? '' },
        { key: 'notes', header: t('production.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<ProcessedMaterialBatch>({
      key: 'processed_material_batches',
      title: tbl('processed_material_batches'),
      fetchRows: () => fetchAllPaginated((p) => processedMaterials.batches.list(p)),
      columns: [
        { key: 'scheduled_for', header: t('processedMaterials.batches.exportCols.scheduled'), value: (r) => r.scheduled_for },
        { key: 'completed_at', header: t('processedMaterials.batches.exportCols.completed'), value: (r) => r.completed_at ?? '' },
        { key: 'processed_material_sku', header: t('processedMaterials.batches.exportCols.materialSku'), value: (r) => r.processed_material_sku },
        { key: 'processed_material_name', header: t('processedMaterials.batches.exportCols.material'), value: (r) => r.processed_material_name },
        { key: 'batches', header: t('processedMaterials.batches.exportCols.batches'), value: (r) => Number(r.batches) },
        { key: 'quantity_produced', header: t('processedMaterials.batches.exportCols.produced'), value: (r) => Number(r.quantity_produced) },
        { key: 'processed_material_unit', header: t('processedMaterials.batches.exportCols.unit'), value: (r) => r.processed_material_unit },
        { key: 'cost', header: t('processedMaterials.batches.exportCols.cost'), value: (r) => Number(r.cost) },
        { key: 'created_by', header: t('processedMaterials.batches.exportCols.by'), value: (r) => r.created_by_name ?? '' },
        { key: 'notes', header: t('processedMaterials.batches.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<Sale>({
      key: 'sales',
      title: tbl('sales'),
      fetchRows: () => fetchAllPaginated((p) => sales.list(p)),
      columns: [
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
      ],
    }),

    dataset<Transaction>({
      key: 'transactions',
      title: tbl('transactions'),
      fetchRows: () => fetchAllPaginated((p) => finance.transactions.list(p)),
      columns: [
        { key: 'occurred_on', header: t('transactions.exportCols.date'), value: (r) => r.occurred_on },
        { key: 'direction', header: t('transactions.exportCols.direction'), value: (r) => r.direction_display },
        { key: 'title', header: t('transactions.exportCols.title'), value: (r) => r.title },
        { key: 'category', header: t('transactions.exportCols.category'), value: (r) => r.category_name },
        { key: 'amount', header: t('transactions.exportCols.amount'), value: (r) => Number(r.amount) },
        { key: 'signed_amount', header: t('transactions.exportCols.signedAmount'), value: (r) => (r.direction === 'income' ? 1 : -1) * Number(r.amount) },
        { key: 'payment_method', header: t('transactions.exportCols.payment'), value: (r) => r.payment_method_display },
        { key: 'counterparty', header: t('transactions.exportCols.counterparty'), value: (r) => r.counterparty },
        { key: 'reference', header: t('transactions.exportCols.reference'), value: (r) => r.reference },
        { key: 'recorded_by', header: t('transactions.exportCols.recordedBy'), value: (r) => r.recorded_by_name ?? '' },
        { key: 'notes', header: t('transactions.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<TransactionCategory>({
      key: 'transaction_categories',
      title: tbl('transaction_categories'),
      fetchRows: () => fetchAllPaginated((p) => finance.transactionCategories.list(p)),
      columns: [
        { key: 'name', header: t('transactions.exportCols.name'), value: (r) => r.name },
        { key: 'direction', header: t('transactions.exportCols.direction'), value: (r) => r.direction_display },
        { key: 'description', header: t('transactions.exportCols.description'), value: (r) => r.description },
        { key: 'is_active', header: t('transactions.exportCols.active'), value: (r) => yesNo(r.is_active) },
      ],
    }),

    dataset<Invoice>({
      key: 'invoices',
      title: tbl('invoices'),
      fetchRows: () => fetchAllPaginated((p) => finance.invoices.list(p)),
      columns: [
        { key: 'invoice_number', header: t('invoices.exportCols.invoiceNumber'), value: (r) => r.invoice_number },
        { key: 'customer_name', header: t('invoices.exportCols.customer'), value: (r) => r.customer_name },
        { key: 'customer_email', header: t('invoices.exportCols.email'), value: (r) => r.customer_email },
        { key: 'customer_phone', header: t('invoices.exportCols.phone'), value: (r) => r.customer_phone },
        { key: 'issue_date', header: t('invoices.exportCols.issued'), value: (r) => r.issue_date },
        { key: 'due_date', header: t('invoices.exportCols.due'), value: (r) => r.due_date },
        { key: 'amount', header: t('invoices.exportCols.amount'), value: (r) => Number(r.amount) },
        { key: 'amount_paid', header: t('invoices.exportCols.paid'), value: (r) => Number(r.amount_paid) },
        { key: 'balance_due', header: t('invoices.exportCols.balance'), value: (r) => Number(r.balance_due) },
        { key: 'status', header: t('invoices.exportCols.status'), value: (r) => r.status_display },
        { key: 'is_overdue', header: t('invoices.exportCols.overdue'), value: (r) => yesNo(r.is_overdue) },
        { key: 'paid_at', header: t('invoices.exportCols.paidAt'), value: (r) => r.paid_at ?? '' },
        { key: 'description', header: t('invoices.exportCols.description'), value: (r) => r.description },
        { key: 'notes', header: t('invoices.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<Budget>({
      key: 'budgets',
      title: tbl('budgets'),
      fetchRows: () => fetchAllPaginated((p) => finance.budgets.list(p)),
      columns: [
        { key: 'category', header: t('budgets.exportCols.category'), value: (r) => r.category_name },
        { key: 'month', header: t('budgets.exportCols.month'), value: (r) => r.month },
        { key: 'amount', header: t('budgets.exportCols.budgeted'), value: (r) => Number(r.amount) },
        { key: 'notes', header: t('budgets.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<Asset>({
      key: 'assets',
      title: tbl('assets'),
      fetchRows: () => fetchAllPaginated((p) => finance.assets.list(p)),
      columns: [
        { key: 'name', header: t('assets.exportCols.name'), value: (r) => r.name },
        { key: 'category', header: t('assets.exportCols.category'), value: (r) => t(`assets.categories.${r.category}`) },
        { key: 'purchase_date', header: t('assets.exportCols.purchased'), value: (r) => r.purchase_date },
        { key: 'purchase_cost', header: t('assets.exportCols.cost'), value: (r) => Number(r.purchase_cost) },
        { key: 'useful_life_months', header: t('assets.exportCols.usefulLifeMonths'), value: (r) => r.useful_life_months ?? '' },
        { key: 'accumulated_depreciation', header: t('assets.exportCols.accumulatedDepreciation'), value: (r) => Number(r.accumulated_depreciation) },
        { key: 'carrying_value', header: t('assets.exportCols.carryingValue'), value: (r) => Number(r.carrying_value) },
        { key: 'supplier', header: t('assets.exportCols.supplier'), value: (r) => r.supplier_name ?? '' },
        { key: 'reference', header: t('assets.exportCols.reference'), value: (r) => r.reference },
        { key: 'status', header: t('assets.exportCols.status'), value: (r) => t(`assets.statuses.${r.status}`) },
        { key: 'notes', header: t('assets.exportCols.notes'), value: (r) => r.notes },
      ],
    }),

    dataset<Wallet>({
      key: 'wallets',
      title: tbl('wallets'),
      fetchRows: () => fetchAllPaginated((p) => finance.wallets.list(p)),
      columns: [
        { key: 'name', header: t('wallets.exportCols.name'), value: (r) => r.name },
        { key: 'account_type', header: t('wallets.exportCols.type'), value: (r) => t(`wallets.accountTypes.${r.account_type}`) },
        { key: 'institution', header: t('wallets.exportCols.institution'), value: (r) => r.institution },
        { key: 'account_number', header: t('wallets.exportCols.accountNumber'), value: (r) => r.account_number },
        { key: 'opening_balance', header: t('wallets.exportCols.opening'), value: (r) => Number(r.opening_balance) },
        { key: 'current_balance', header: t('wallets.exportCols.balance'), value: (r) => Number(r.current_balance) },
        { key: 'is_active', header: t('wallets.exportCols.active'), value: (r) => yesNo(r.is_active) },
        { key: 'notes', header: t('wallets.exportCols.notes'), value: (r) => r.notes },
      ],
    }),
  ];

  if (includeUsers) {
    datasets.push(
      dataset<User>({
        key: 'users',
        title: tbl('users'),
        fetchRows: () => fetchAllPaginated((p) => users.list(p)),
        columns: [
          { key: 'full_name', header: t('users.exportCols.name'), value: (r) => r.full_name },
          { key: 'email', header: t('users.exportCols.email'), value: (r) => r.email },
          { key: 'phone', header: t('users.exportCols.phone'), value: (r) => r.phone },
          { key: 'role', header: t('users.exportCols.role'), value: (r) => r.role },
          { key: 'is_active', header: t('users.exportCols.active'), value: (r) => yesNo(r.is_active) },
          { key: 'date_joined', header: t('users.exportCols.joined'), value: (r) => r.date_joined },
        ],
      }),
    );
  }

  return datasets;
}
