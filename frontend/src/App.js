import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { ProductsPage } from './pages/Products';
import { RawMaterialsPage } from './pages/RawMaterials';
import { SuppliersPage } from './pages/Suppliers';
import { InventoryPage } from './pages/Inventory';
import { ProductionPage } from './pages/Production';
import { SalesPage } from './pages/Sales';
import { TransactionsPage } from './pages/Transactions';
import { InvoicesPage } from './pages/Invoices';
import { BudgetsPage } from './pages/Budgets';
import { AssetsPage } from './pages/Assets';
import { WalletsPage } from './pages/Wallets';
import { UsersPage } from './pages/Users';
import { ProcessedMaterialsPage } from './pages/ProcessedMaterials';
export default function App() {
    return (_jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(Login, {}) }), _jsxs(Route, { path: "/", element: _jsx(ProtectedRoute, { children: _jsx(AppLayout, {}) }), children: [_jsx(Route, { index: true, element: _jsx(Dashboard, {}) }), _jsx(Route, { path: "sales", element: _jsx(SalesPage, {}) }), _jsx(Route, { path: "production", element: _jsx(ProductionPage, {}) }), _jsx(Route, { path: "inventory", element: _jsx(InventoryPage, {}) }), _jsx(Route, { path: "products", element: _jsx(ProductsPage, {}) }), _jsx(Route, { path: "raw-materials", element: _jsx(RawMaterialsPage, {}) }), _jsx(Route, { path: "processed-materials", element: _jsx(ProcessedMaterialsPage, {}) }), _jsx(Route, { path: "suppliers", element: _jsx(SuppliersPage, {}) }), _jsx(Route, { path: "transactions", element: _jsx(TransactionsPage, {}) }), _jsx(Route, { path: "invoices", element: _jsx(InvoicesPage, {}) }), _jsx(Route, { path: "budgets", element: _jsx(BudgetsPage, {}) }), _jsx(Route, { path: "assets", element: _jsx(AssetsPage, {}) }), _jsx(Route, { path: "wallets", element: _jsx(WalletsPage, {}) }), _jsx(Route, { path: "users", element: _jsx(UsersPage, {}) })] }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/", replace: true }) })] }));
}
