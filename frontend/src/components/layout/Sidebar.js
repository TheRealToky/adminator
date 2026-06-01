import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ShoppingBag, Package, Boxes, Factory, Receipt, FileText, Users2, Building2, Tag, ChefHat, ArrowLeftRight, X, } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { useAuth } from '@/store/AuthContext';
export function Sidebar({ open, onClose }) {
    const { user } = useAuth();
    const { t } = useTranslation();
    const isAdmin = user?.is_admin ?? false;
    const nav = [
        { to: '/', label: t('sidebar.dashboard'), icon: LayoutDashboard, exact: true },
        { section: t('sidebar.sections.operations') },
        { to: '/sales', label: t('sidebar.sales'), icon: ShoppingBag },
        { to: '/production', label: t('sidebar.production'), icon: Factory },
        { to: '/inventory', label: t('sidebar.inventory'), icon: Boxes },
        { section: t('sidebar.sections.catalog') },
        { to: '/products', label: t('sidebar.products'), icon: Package },
        { to: '/processed-materials', label: t('sidebar.processedMaterials'), icon: ChefHat },
        { to: '/raw-materials', label: t('sidebar.rawMaterials'), icon: Tag },
        { to: '/suppliers', label: t('sidebar.suppliers'), icon: Building2 },
        { section: t('sidebar.sections.finance') },
        { to: '/transactions', label: t('sidebar.transactions'), icon: ArrowLeftRight },
        { to: '/invoices', label: t('sidebar.invoices'), icon: FileText },
        { to: '/budgets', label: t('sidebar.budgets'), icon: Receipt },
        { section: t('sidebar.sections.admin'), adminOnly: true },
        { to: '/users', label: t('sidebar.staff'), icon: Users2, adminOnly: true },
    ];
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: cn('fixed inset-0 bg-slate-900/40 z-40 lg:hidden transition-opacity', open ? 'opacity-100' : 'opacity-0 pointer-events-none'), onClick: onClose }), _jsxs("aside", { className: cn('fixed lg:sticky top-0 left-0 z-50 h-screen w-64 bg-white border-r border-slate-200', 'transform transition-transform lg:translate-x-0', open ? 'translate-x-0' : '-translate-x-full'), children: [_jsxs("div", { className: "flex items-center justify-between h-16 px-5 border-b border-slate-200", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: "h-8 w-8 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold", children: "A" }), _jsx("span", { className: "font-semibold text-slate-900", children: t('common.appName') })] }), _jsx("button", { onClick: onClose, className: "lg:hidden text-slate-500", children: _jsx(X, { size: 20 }) })] }), _jsx("nav", { className: "px-3 py-4 space-y-0.5 overflow-y-auto h-[calc(100vh-4rem)]", children: nav.map((item, idx) => {
                            if ('section' in item) {
                                if (item.adminOnly && !isAdmin)
                                    return null;
                                return (_jsx("p", { className: "px-3 pt-5 pb-1.5 text-[11px] uppercase tracking-wider font-semibold text-slate-400", children: item.section }, `sec-${idx}`));
                            }
                            if (item.adminOnly && !isAdmin)
                                return null;
                            const Icon = item.icon;
                            return (_jsxs(NavLink, { to: item.to, end: item.exact, onClick: onClose, className: ({ isActive }) => cn('flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors', isActive
                                    ? 'bg-brand-50 text-brand-700'
                                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'), children: [_jsx(Icon, { size: 18 }), item.label] }, item.to));
                        }) })] })] }));
}
