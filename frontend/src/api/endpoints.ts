import { api } from './client';
import type {
  Budget, Choice, DashboardOverview, Expense, ExpenseCategory, Invoice, LoginResponse,
  Paginated, Product, ProductCategory, ProductionRun, RawMaterial, RecipeItem,
  Sale, StockItem, StockMovement, Supplier, Transaction, TransactionCategory, User,
} from './types';

// ── Auth ──────────────────────────────────────────────────────────────────
export const auth = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login/', { email, password }).then((r) => r.data),
  me: () => api.get<User>('/auth/me/').then((r) => r.data),
  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password/', { current_password, new_password }),
  roles: () => api.get<Choice[]>('/auth/roles/').then((r) => r.data),
};

// ── Users ─────────────────────────────────────────────────────────────────
export const users = {
  list: (params: Record<string, unknown> = {}) =>
    api.get<Paginated<User>>('/auth/users/', { params }).then((r) => r.data),
  get: (id: string) => api.get<User>(`/auth/users/${id}/`).then((r) => r.data),
  create: (data: Partial<User> & { password: string }) =>
    api.post<User>('/auth/users/', data).then((r) => r.data),
  update: (id: string, data: Partial<User>) =>
    api.patch<User>(`/auth/users/${id}/`, data).then((r) => r.data),
  remove: (id: string) => api.delete(`/auth/users/${id}/`),
  activate: (id: string) => api.post(`/auth/users/${id}/activate/`),
  deactivate: (id: string) => api.post(`/auth/users/${id}/deactivate/`),
};

// ── Catalog ───────────────────────────────────────────────────────────────
export const catalog = {
  units: () => api.get<Choice[]>('/catalog/units/').then((r) => r.data),

  categories: {
    list: (params = {}) =>
      api.get<Paginated<ProductCategory>>('/catalog/categories/', { params }).then((r) => r.data),
    get: (id: string) => api.get<ProductCategory>(`/catalog/categories/${id}/`).then((r) => r.data),
    create: (data: Partial<ProductCategory>) =>
      api.post<ProductCategory>('/catalog/categories/', data).then((r) => r.data),
    update: (id: string, data: Partial<ProductCategory>) =>
      api.patch<ProductCategory>(`/catalog/categories/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/catalog/categories/${id}/`),
  },

  suppliers: {
    list: (params = {}) =>
      api.get<Paginated<Supplier>>('/catalog/suppliers/', { params }).then((r) => r.data),
    get: (id: string) => api.get<Supplier>(`/catalog/suppliers/${id}/`).then((r) => r.data),
    create: (data: Partial<Supplier>) =>
      api.post<Supplier>('/catalog/suppliers/', data).then((r) => r.data),
    update: (id: string, data: Partial<Supplier>) =>
      api.patch<Supplier>(`/catalog/suppliers/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/catalog/suppliers/${id}/`),
  },

  rawMaterials: {
    list: (params = {}) =>
      api.get<Paginated<RawMaterial>>('/catalog/raw-materials/', { params }).then((r) => r.data),
    get: (id: string) => api.get<RawMaterial>(`/catalog/raw-materials/${id}/`).then((r) => r.data),
    create: (data: Partial<RawMaterial>) =>
      api.post<RawMaterial>('/catalog/raw-materials/', data).then((r) => r.data),
    update: (id: string, data: Partial<RawMaterial>) =>
      api.patch<RawMaterial>(`/catalog/raw-materials/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/catalog/raw-materials/${id}/`),
  },

  products: {
    list: (params = {}) =>
      api.get<Paginated<Product>>('/catalog/products/', { params }).then((r) => r.data),
    get: (id: string) => api.get<Product>(`/catalog/products/${id}/`).then((r) => r.data),
    create: (data: Partial<Product>) =>
      api.post<Product>('/catalog/products/', data).then((r) => r.data),
    update: (id: string, data: Partial<Product>) =>
      api.patch<Product>(`/catalog/products/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/catalog/products/${id}/`),
  },

  recipes: {
    list: (params = {}) =>
      api.get<Paginated<RecipeItem>>('/catalog/recipes/', { params }).then((r) => r.data),
    create: (data: Partial<RecipeItem>) =>
      api.post<RecipeItem>('/catalog/recipes/', data).then((r) => r.data),
    update: (id: string, data: Partial<RecipeItem>) =>
      api.patch<RecipeItem>(`/catalog/recipes/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/catalog/recipes/${id}/`),
  },
};

// ── Inventory ─────────────────────────────────────────────────────────────
export const inventory = {
  stock: {
    list: (params = {}) =>
      api.get<Paginated<StockItem>>('/inventory/stock/', { params }).then((r) => r.data),
    low: () => api.get<Paginated<StockItem>>('/inventory/stock/low-stock/').then((r) => r.data),
    adjust: (data: { product?: string; raw_material?: string; quantity_delta: number; note?: string; reference?: string }) =>
      api.post('/inventory/stock/adjust/', data).then((r) => r.data),
    receive: (data: { raw_material: string; quantity: number; reference?: string; note?: string }) =>
      api.post('/inventory/stock/receive/', data).then((r) => r.data),
    writeOff: (data: { product?: string; raw_material?: string; quantity: number; note?: string; reference?: string }) =>
      api.post('/inventory/stock/write-off/', data).then((r) => r.data),
  },
  movements: {
    list: (params = {}) =>
      api.get<Paginated<StockMovement>>('/inventory/movements/', { params }).then((r) => r.data),
  },
};

// ── Production ────────────────────────────────────────────────────────────
export const production = {
  runs: {
    list: (params = {}) =>
      api.get<Paginated<ProductionRun>>('/production/runs/', { params }).then((r) => r.data),
    get: (id: string) => api.get<ProductionRun>(`/production/runs/${id}/`).then((r) => r.data),
    execute: (data: { product: string; quantity: number; notes?: string; scheduled_for?: string; status?: string }) =>
      api.post<ProductionRun>('/production/runs/execute/', data).then((r) => r.data),
    remove: (id: string) => api.delete(`/production/runs/${id}/`),
  },
};

// ── Sales ─────────────────────────────────────────────────────────────────
export const sales = {
  paymentMethods: () => api.get<Choice[]>('/sales/payment-methods/').then((r) => r.data),
  channels: () => api.get<Choice[]>('/sales/channels/').then((r) => r.data),
  list: (params = {}) =>
    api.get<Paginated<Sale>>('/sales/sales/', { params }).then((r) => r.data),
  get: (id: string) => api.get<Sale>(`/sales/sales/${id}/`).then((r) => r.data),
  record: (data: {
    items: Array<{ product: string; quantity: number; unit_price?: number }>;
    payment_method?: string;
    channel?: string;
    discount?: number;
    customer_name?: string;
    customer_phone?: string;
    notes?: string;
  }) => api.post<Sale>('/sales/sales/record/', data).then((r) => r.data),
  remove: (id: string) => api.delete(`/sales/sales/${id}/`),
};

// ── Finance ───────────────────────────────────────────────────────────────
export const finance = {
  expenseCategories: {
    list: (params = {}) =>
      api.get<Paginated<ExpenseCategory>>('/finance/expense-categories/', { params }).then((r) => r.data),
    create: (data: Partial<ExpenseCategory>) =>
      api.post<ExpenseCategory>('/finance/expense-categories/', data).then((r) => r.data),
    update: (id: string, data: Partial<ExpenseCategory>) =>
      api.patch<ExpenseCategory>(`/finance/expense-categories/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/expense-categories/${id}/`),
  },
  expenses: {
    list: (params = {}) =>
      api.get<Paginated<Expense>>('/finance/expenses/', { params }).then((r) => r.data),
    create: (data: Partial<Expense>) =>
      api.post<Expense>('/finance/expenses/', data).then((r) => r.data),
    update: (id: string, data: Partial<Expense>) =>
      api.patch<Expense>(`/finance/expenses/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/expenses/${id}/`),
  },
  invoices: {
    list: (params = {}) =>
      api.get<Paginated<Invoice>>('/finance/invoices/', { params }).then((r) => r.data),
    get: (id: string) => api.get<Invoice>(`/finance/invoices/${id}/`).then((r) => r.data),
    overdue: () =>
      api.get<Paginated<Invoice>>('/finance/invoices/overdue/').then((r) => r.data),
    create: (data: Partial<Invoice>) =>
      api.post<Invoice>('/finance/invoices/', data).then((r) => r.data),
    update: (id: string, data: Partial<Invoice>) =>
      api.patch<Invoice>(`/finance/invoices/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/invoices/${id}/`),
    recordPayment: (id: string, amount: number) =>
      api.post<Invoice>(`/finance/invoices/${id}/record-payment/`, { amount }).then((r) => r.data),
    markSent: (id: string) =>
      api.post<Invoice>(`/finance/invoices/${id}/mark-sent/`).then((r) => r.data),
    cancel: (id: string) =>
      api.post<Invoice>(`/finance/invoices/${id}/cancel/`).then((r) => r.data),
  },
  budgets: {
    list: (params = {}) =>
      api.get<Paginated<Budget>>('/finance/budgets/', { params }).then((r) => r.data),
    create: (data: Partial<Budget>) =>
      api.post<Budget>('/finance/budgets/', data).then((r) => r.data),
    update: (id: string, data: Partial<Budget>) =>
      api.patch<Budget>(`/finance/budgets/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/budgets/${id}/`),
  },
  transactionCategories: {
    list: (params = {}) =>
      api.get<Paginated<TransactionCategory>>('/finance/transaction-categories/', { params }).then((r) => r.data),
    create: (data: Partial<TransactionCategory>) =>
      api.post<TransactionCategory>('/finance/transaction-categories/', data).then((r) => r.data),
    update: (id: string, data: Partial<TransactionCategory>) =>
      api.patch<TransactionCategory>(`/finance/transaction-categories/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/transaction-categories/${id}/`),
  },
  transactions: {
    list: (params = {}) =>
      api.get<Paginated<Transaction>>('/finance/transactions/', { params }).then((r) => r.data),
    create: (data: Partial<Transaction>) =>
      api.post<Transaction>('/finance/transactions/', data).then((r) => r.data),
    update: (id: string, data: Partial<Transaction>) =>
      api.patch<Transaction>(`/finance/transactions/${id}/`, data).then((r) => r.data),
    remove: (id: string) => api.delete(`/finance/transactions/${id}/`),
  },
};

// ── Analytics ─────────────────────────────────────────────────────────────
export const analytics = {
  dashboard: (days = 30) =>
    api.get<DashboardOverview>('/analytics/dashboard/', { params: { days } }).then((r) => r.data),
  forecast: (params: { days?: number; horizon?: number } = {}) =>
    api.get('/analytics/forecast/', { params }).then((r) => r.data),
};
