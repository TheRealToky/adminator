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
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="sales" element={<SalesPage />} />
        <Route path="production" element={<ProductionPage />} />
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="raw-materials" element={<RawMaterialsPage />} />
        <Route path="processed-materials" element={<ProcessedMaterialsPage />} />
        <Route path="suppliers" element={<SuppliersPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="budgets" element={<BudgetsPage />} />
        <Route path="assets" element={<AssetsPage />} />
        <Route path="wallets" element={<WalletsPage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
