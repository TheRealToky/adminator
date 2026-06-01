export type UUID = string;

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: UUID;
  email: string;
  full_name: string;
  phone: string;
  role: 'admin' | 'manager' | 'accountant' | 'cashier' | 'staff';
  is_active: boolean;
  is_admin: boolean;
  date_joined: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface ProductCategory {
  id: UUID;
  name: string;
  description: string;
  product_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Supplier {
  id: UUID;
  name: string;
  contact_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  is_active: boolean;
}

export interface RawMaterial {
  id: UUID;
  sku: string;
  name: string;
  unit: string;
  unit_cost: string;
  reorder_threshold: string;
  preferred_supplier: UUID | null;
  preferred_supplier_name: string | null;
  is_active: boolean;
}

export interface RecipeItem {
  id: UUID;
  product?: UUID;
  raw_material: UUID;
  raw_material_name?: string;
  raw_material_unit?: string;
  raw_material_unit_cost?: string;
  quantity: string;
}

export interface Product {
  id: UUID;
  sku: string;
  name: string;
  category: UUID;
  category_name?: string;
  description: string;
  unit: string;
  selling_price: string;
  production_cost: string;
  margin?: string;
  overhead_pct: string;
  reorder_threshold: number;
  is_active: boolean;
  recipe_items?: RecipeItem[];
}

export interface StockItem {
  id: UUID;
  kind: 'product' | 'raw_material';
  product: UUID | null;
  raw_material: UUID | null;
  item_name: string;
  item_sku: string;
  item_unit: string;
  quantity: string;
  reorder_threshold: string;
  is_low: boolean;
}

export interface StockMovement {
  id: UUID;
  stock_item: UUID;
  item_name: string;
  item_sku: string;
  item_unit: string;
  reason: string;
  reason_display: string;
  quantity_delta: string;
  balance_after: string;
  reference: string;
  note: string;
  created_by: UUID | null;
  created_by_name: string | null;
  created_at: string;
}

export interface ProductionRun {
  id: UUID;
  product: UUID;
  product_name: string;
  product_sku: string;
  quantity: string;
  status: 'planned' | 'completed' | 'cancelled';
  scheduled_for: string;
  completed_at: string | null;
  cost: string;
  notes: string;
  created_by: UUID | null;
  created_by_name: string | null;
  created_at: string;
}

export interface SaleItem {
  id: UUID;
  product: UUID;
  product_name: string;
  product_sku: string;
  quantity: string;
  unit_price: string;
  unit_cost: string;
  line_total: string;
}

export interface Sale {
  id: UUID;
  receipt_number: string;
  occurred_at: string;
  channel: string;
  channel_display: string;
  payment_method: string;
  payment_method_display: string;
  customer_name: string;
  customer_phone: string;
  subtotal: string;
  discount: string;
  total: string;
  cost_of_goods: string;
  profit: string;
  notes: string;
  served_by: UUID | null;
  served_by_name: string | null;
  items: SaleItem[];
}

export interface ExpenseCategory {
  id: UUID;
  name: string;
  description: string;
  is_active: boolean;
}

export interface Expense {
  id: UUID;
  category: UUID;
  category_name: string;
  title: string;
  amount: string;
  incurred_on: string;
  payment_method: string;
  payment_method_display: string;
  supplier: UUID | null;
  supplier_name: string | null;
  reference: string;
  notes: string;
  recorded_by: UUID | null;
  recorded_by_name: string | null;
}

export type TransactionDirection = 'income' | 'expense';

export interface TransactionCategory {
  id: UUID;
  name: string;
  direction: TransactionDirection;
  direction_display: string;
  description: string;
  is_active: boolean;
}

export interface Transaction {
  id: UUID;
  direction: TransactionDirection;
  direction_display: string;
  category: UUID;
  category_name: string;
  category_direction: TransactionDirection;
  title: string;
  amount: string;
  occurred_on: string;
  payment_method: string;
  payment_method_display: string;
  counterparty: string;
  reference: string;
  notes: string;
  recorded_by: UUID | null;
  recorded_by_name: string | null;
}

export interface Invoice {
  id: UUID;
  invoice_number: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  issue_date: string;
  due_date: string;
  amount: string;
  amount_paid: string;
  balance_due: string;
  status: string;
  status_display: string;
  is_overdue: boolean;
  description: string;
  notes: string;
  paid_at: string | null;
}

export interface Budget {
  id: UUID;
  category: UUID;
  category_name: string;
  month: string;
  amount: string;
  notes: string;
}

export type AssetCategoryKey =
  | 'equipment'
  | 'furniture'
  | 'vehicle'
  | 'electronics'
  | 'fit_out'
  | 'other';

export type AssetStatus = 'active' | 'disposed';

export interface Asset {
  id: UUID;
  name: string;
  category: AssetCategoryKey;
  category_display: string;
  purchase_date: string;
  purchase_cost: string;
  useful_life_months: number | null;
  status: AssetStatus;
  status_display: string;
  supplier: UUID | null;
  supplier_name: string | null;
  reference: string;
  notes: string;
  linked_expense: UUID | null;
  linked_expense_title: string | null;
  recorded_by: UUID | null;
  recorded_by_name: string | null;
  months_elapsed: number;
  accumulated_depreciation: string;
  carrying_value: string;
  is_fully_depreciated: boolean;
  created_at: string;
  updated_at: string;
}

export interface Choice {
  value: string;
  label: string;
}

export interface DashboardOverview {
  kpis: {
    window_days: number;
    revenue: string;
    cost_of_goods: string;
    gross_profit: string;
    operating_expenses: string;
    net_profit: string;
    receipts: number;
    average_ticket: string;
    revenue_change_pct: number | null;
  };
  sales_timeseries: Array<{
    day: string; revenue: string; cost_of_goods: string; profit: string; receipts: number;
  }>;
  busy_hours: Array<{ hour: number; label: string; revenue: string; receipts: number }>;
  top_products: Array<{ product_id: UUID; name: string; sku: string; quantity: string; revenue: string }>;
  payment_mix: Array<{ method: string; revenue: string; receipts: number }>;
  stock_health: {
    total_items: number;
    low_stock_count: number;
    lowest_items: Array<{
      id: UUID; kind: string; name: string; sku: string; unit: string;
      quantity: string; reorder_threshold: string;
    }>;
  };
  inventory: {
    finished_goods_value: string;
    finished_goods_units: string;
    raw_materials_value: string;
    total_value: string;
  };
  production_summary: {
    total_runs: number;
    completed_runs: number;
    units_produced: string;
    total_cost: string;
    by_day: Array<{ day: string; units: string; cost: string; runs: number }>;
  };
  expense_breakdown: Array<{ category_id: UUID; name: string; total: string }>;
  invoices: {
    by_status: Array<{ status: string; count: number; total: string }>;
    overdue_total: string;
  };
}
