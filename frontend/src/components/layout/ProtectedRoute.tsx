import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@/store/AuthContext';

export function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isAuthenticated, loading } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-slate-400">
        <Loader2 className="animate-spin mr-2" /> {t('common.loading')}
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
