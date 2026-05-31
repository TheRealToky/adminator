import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@/store/AuthContext';
import { extractErrorMessage } from '@/api/client';

export function Login() {
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('admin@adminator.local');
  const [password, setPassword] = useState('admin12345');
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/';

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      toast.error(extractErrorMessage(err, t('login.invalidCredentials')));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-white to-amber-50 p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex h-14 w-14 rounded-2xl bg-brand-500 text-white items-center justify-center text-2xl font-bold mb-3">
            A
          </div>
          <h1 className="text-2xl font-bold text-slate-900">{t('common.appName')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('login.subtitle')}</p>
        </div>

        <form onSubmit={onSubmit} className="card card-body space-y-4">
          <div>
            <label htmlFor="email" className="label">{t('common.email')}</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
              autoComplete="email"
            />
          </div>
          <div>
            <label htmlFor="password" className="label">{t('login.password')}</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary w-full"
          >
            {submitting ? (<><Loader2 className="animate-spin mr-2" size={16} /> {t('login.signingIn')}</>) : t('login.signIn')}
          </button>
          <p className="text-xs text-slate-500 text-center">
            {t('login.demoSeed')}
          </p>
        </form>
      </div>
    </div>
  );
}
