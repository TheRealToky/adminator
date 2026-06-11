import { api } from './client';
// ── Auth ──────────────────────────────────────────────────────────────────
export const auth = {
    login: (email, password) => api.post('/auth/login/', { email, password }).then((r) => r.data),
    me: () => api.get('/auth/me/').then((r) => r.data),
    changePassword: (current_password, new_password) => api.post('/auth/change-password/', { current_password, new_password }),
    roles: () => api.get('/auth/roles/').then((r) => r.data),
};
// ── Users ─────────────────────────────────────────────────────────────────
export const users = {
    list: (params = {}) => api.get('/auth/users/', { params }).then((r) => r.data),
    get: (id) => api.get(`/auth/users/${id}/`).then((r) => r.data),
    create: (data) => api.post('/auth/users/', data).then((r) => r.data),
    update: (id, data) => api.patch(`/auth/users/${id}/`, data).then((r) => r.data),
    remove: (id) => api.delete(`/auth/users/${id}/`),
    activate: (id) => api.post(`/auth/users/${id}/activate/`),
    deactivate: (id) => api.post(`/auth/users/${id}/deactivate/`),
};
// ── Catalog ───────────────────────────────────────────────────────────────
export const catalog = {
    units: () => api.get('/catalog/units/').then((r) => r.data),
    categories: {
        list: (params = {}) => api.get('/catalog/categories/', { params }).then((r) => r.data),
        get: (id) => api.get(`/catalog/categories/${id}/`).then((r) => r.data),
        create: (data) => api.post('/catalog/categories/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/catalog/categories/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/catalog/categories/${id}/`),
    },
    suppliers: {
        list: (params = {}) => api.get('/catalog/suppliers/', { params }).then((r) => r.data),
        get: (id) => api.get(`/catalog/suppliers/${id}/`).then((r) => r.data),
        create: (data) => api.post('/catalog/suppliers/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/catalog/suppliers/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/catalog/suppliers/${id}/`),
    },
    rawMaterials: {
        list: (params = {}) => api.get('/catalog/raw-materials/', { params }).then((r) => r.data),
        get: (id) => api.get(`/catalog/raw-materials/${id}/`).then((r) => r.data),
        create: (data) => api.post('/catalog/raw-materials/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/catalog/raw-materials/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/catalog/raw-materials/${id}/`),
    },
    products: {
        list: (params = {}) => api.get('/catalog/products/', { params }).then((r) => r.data),
        get: (id) => api.get(`/catalog/products/${id}/`).then((r) => r.data),
        create: (data) => api.post('/catalog/products/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/catalog/products/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/catalog/products/${id}/`),
    },
    recipes: {
        list: (params = {}) => api.get('/catalog/recipes/', { params }).then((r) => r.data),
        create: (data) => api.post('/catalog/recipes/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/catalog/recipes/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/catalog/recipes/${id}/`),
    },
};
// ── Inventory ─────────────────────────────────────────────────────────────
export const inventory = {
    stock: {
        list: (params = {}) => api.get('/inventory/stock/', { params }).then((r) => r.data),
        low: () => api.get('/inventory/stock/low-stock/').then((r) => r.data),
        adjust: (data) => api.post('/inventory/stock/adjust/', data).then((r) => r.data),
        receive: (data) => api.post('/inventory/stock/receive/', data).then((r) => r.data),
        writeOff: (data) => api.post('/inventory/stock/write-off/', data).then((r) => r.data),
    },
    movements: {
        list: (params = {}) => api.get('/inventory/movements/', { params }).then((r) => r.data),
    },
};
// ── Production ────────────────────────────────────────────────────────────
export const production = {
    runs: {
        list: (params = {}) => api.get('/production/runs/', { params }).then((r) => r.data),
        get: (id) => api.get(`/production/runs/${id}/`).then((r) => r.data),
        execute: (data) => api.post('/production/runs/execute/', data).then((r) => r.data),
        remove: (id) => api.delete(`/production/runs/${id}/`),
    },
};
// ── Sales ─────────────────────────────────────────────────────────────────
export const sales = {
    paymentMethods: () => api.get('/sales/payment-methods/').then((r) => r.data),
    channels: () => api.get('/sales/channels/').then((r) => r.data),
    list: (params = {}) => api.get('/sales/sales/', { params }).then((r) => r.data),
    get: (id) => api.get(`/sales/sales/${id}/`).then((r) => r.data),
    record: (data) => api.post('/sales/sales/record/', data).then((r) => r.data),
    remove: (id) => api.delete(`/sales/sales/${id}/`),
};
// ── Finance ───────────────────────────────────────────────────────────────
export const finance = {
    expenseCategories: {
        list: (params = {}) => api.get('/finance/expense-categories/', { params }).then((r) => r.data),
        create: (data) => api.post('/finance/expense-categories/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/expense-categories/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/expense-categories/${id}/`),
    },
    expenses: {
        list: (params = {}) => api.get('/finance/expenses/', { params }).then((r) => r.data),
        create: (data) => api.post('/finance/expenses/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/expenses/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/expenses/${id}/`),
    },
    invoices: {
        list: (params = {}) => api.get('/finance/invoices/', { params }).then((r) => r.data),
        get: (id) => api.get(`/finance/invoices/${id}/`).then((r) => r.data),
        overdue: () => api.get('/finance/invoices/overdue/').then((r) => r.data),
        create: (data) => api.post('/finance/invoices/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/invoices/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/invoices/${id}/`),
        recordPayment: (id, amount) => api.post(`/finance/invoices/${id}/record-payment/`, { amount }).then((r) => r.data),
        markSent: (id) => api.post(`/finance/invoices/${id}/mark-sent/`).then((r) => r.data),
        cancel: (id) => api.post(`/finance/invoices/${id}/cancel/`).then((r) => r.data),
    },
    budgets: {
        list: (params = {}) => api.get('/finance/budgets/', { params }).then((r) => r.data),
        create: (data) => api.post('/finance/budgets/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/budgets/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/budgets/${id}/`),
    },
    transactionCategories: {
        list: (params = {}) => api.get('/finance/transaction-categories/', { params }).then((r) => r.data),
        create: (data) => api.post('/finance/transaction-categories/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/transaction-categories/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/transaction-categories/${id}/`),
    },
    transactions: {
        list: (params = {}) => api.get('/finance/transactions/', { params }).then((r) => r.data),
        create: (data) => api.post('/finance/transactions/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/transactions/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/transactions/${id}/`),
    },
    assets: {
        list: (params = {}) => api.get('/finance/assets/', { params }).then((r) => r.data),
        get: (id) => api.get(`/finance/assets/${id}/`).then((r) => r.data),
        create: (data) => api.post('/finance/assets/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/assets/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/assets/${id}/`),
        dispose: (id) => api.post(`/finance/assets/${id}/dispose/`).then((r) => r.data),
        reactivate: (id) => api.post(`/finance/assets/${id}/reactivate/`).then((r) => r.data),
    },
    wallets: {
        accountTypes: () => api.get('/finance/wallets/account-types/').then((r) => r.data),
        list: (params = {}) => api.get('/finance/wallets/', { params }).then((r) => r.data),
        get: (id) => api.get(`/finance/wallets/${id}/`).then((r) => r.data),
        create: (data) => api.post('/finance/wallets/', data).then((r) => r.data),
        update: (id, data) => api.patch(`/finance/wallets/${id}/`, data).then((r) => r.data),
        remove: (id) => api.delete(`/finance/wallets/${id}/`),
        deposit: (id, data) => api.post(`/finance/wallets/${id}/deposit/`, data).then((r) => r.data),
        withdraw: (id, data) => api.post(`/finance/wallets/${id}/withdraw/`, data).then((r) => r.data),
        transfer: (id, data) => api.post(`/finance/wallets/${id}/transfer/`, data).then((r) => r.data),
        entries: (id, params = {}) => api.get(`/finance/wallets/${id}/entries/`, { params }).then((r) => r.data),
        ledger: (id) => api.get(`/finance/wallets/${id}/ledger/`).then((r) => r.data),
    },
    walletEntries: {
        list: (params = {}) => api.get('/finance/wallet-entries/', { params }).then((r) => r.data),
    },
};
// ── Analytics ─────────────────────────────────────────────────────────────
export const analytics = {
    dashboard: (days = 30) => api.get('/analytics/dashboard/', { params: { days } }).then((r) => r.data),
    forecast: (params = {}) => api.get('/analytics/forecast/', { params }).then((r) => r.data),
};
