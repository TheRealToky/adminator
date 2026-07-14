import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, ShoppingBag, Package, Boxes, Factory,
  Receipt, FileText, Users2, Building2, Tag, ChefHat,
  ArrowLeftRight, Building, Wallet, BookOpen, X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/cn';
import { useAuth } from '@/store/AuthContext';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

type NavItem =
  | { section: string; adminOnly?: boolean }
  | { to: string; label: string; icon: typeof LayoutDashboard; exact?: boolean; adminOnly?: boolean };

export function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const isAdmin = user?.is_admin ?? false;

  const nav: NavItem[] = [
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
    { to: '/wallets', label: t('sidebar.wallets'), icon: Wallet },
    { to: '/transactions', label: t('sidebar.transactions'), icon: ArrowLeftRight },
    { to: '/invoices', label: t('sidebar.invoices'), icon: FileText },
    { to: '/budgets', label: t('sidebar.budgets'), icon: Receipt },
    { to: '/assets', label: t('sidebar.assets'), icon: Building },
    { to: '/ledger', label: t('sidebar.ledger'), icon: BookOpen },
    { section: t('sidebar.sections.admin'), adminOnly: true },
    { to: '/users', label: t('sidebar.staff'), icon: Users2, adminOnly: true },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-slate-900/40 z-40 lg:hidden transition-opacity',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none',
        )}
        onClick={onClose}
      />
      <aside
        className={cn(
          'fixed lg:sticky top-0 left-0 z-50 h-screen w-64 bg-white border-r border-slate-200',
          'transform transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between h-16 px-5 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold">
              A
            </div>
            <span className="font-semibold text-slate-900">{t('common.appName')}</span>
          </div>
          <button onClick={onClose} className="lg:hidden text-slate-500">
            <X size={20} />
          </button>
        </div>
        <nav className="px-3 py-4 space-y-0.5 overflow-y-auto h-[calc(100vh-4rem)]">
          {nav.map((item, idx) => {
            if ('section' in item) {
              if (item.adminOnly && !isAdmin) return null;
              return (
                <p
                  key={`sec-${idx}`}
                  className="px-3 pt-5 pb-1.5 text-[11px] uppercase tracking-wider font-semibold text-slate-400"
                >
                  {item.section}
                </p>
              );
            }
            if (item.adminOnly && !isAdmin) return null;
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-brand-50 text-brand-700'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  )
                }
              >
                <Icon size={18} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
