import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/store/AuthContext';
export function ProtectedRoute({ children }) {
    const { isAuthenticated, loading } = useAuth();
    const { t } = useTranslation();
    const location = useLocation();
    if (loading) {
        return (_jsxs("div", { className: "flex items-center justify-center min-h-screen text-slate-400", children: [_jsx(Loader2, { className: "animate-spin mr-2" }), " ", t('common.loading')] }));
    }
    if (!isAuthenticated) {
        return _jsx(Navigate, { to: "/login", state: { from: location }, replace: true });
    }
    return children;
}
