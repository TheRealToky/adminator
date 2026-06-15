import { Menu, LogOut, User as UserIcon, Globe, Check } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@/store/AuthContext';
import { ExportAllMenu } from '@/components/ui/ExportAllMenu';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '@/i18n';

interface Props {
  onMenu: () => void;
}

export function Topbar({ onMenu }: Props) {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);

  const currentLang = (i18n.resolvedLanguage ?? i18n.language ?? 'en').split('-')[0] as SupportedLanguage;

  function changeLang(lng: SupportedLanguage) {
    void i18n.changeLanguage(lng);
    setLangOpen(false);
  }

  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-slate-200">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6">
        <button onClick={onMenu} className="lg:hidden text-slate-600">
          <Menu size={22} />
        </button>
        <div className="flex-1" />

        <div className="mr-2">
          <ExportAllMenu size="sm" />
        </div>

        <div className="relative mr-2">
          <button
            onClick={() => setLangOpen((v) => !v)}
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-slate-100 text-slate-600"
            aria-label={t('topbar.language')}
            aria-haspopup="menu"
            aria-expanded={langOpen}
          >
            <Globe size={18} />
            <span className="text-xs font-semibold uppercase">{currentLang}</span>
          </button>
          {langOpen && (
            <div
              onClick={() => setLangOpen(false)}
              className="fixed inset-0 z-40"
            />
          )}
          {langOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-44 bg-white rounded-md shadow-lg border border-slate-200 py-1 z-50"
            >
              <p className="px-3 py-1.5 text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                {t('topbar.language')}
              </p>
              {SUPPORTED_LANGUAGES.map((lng) => (
                <button
                  key={lng}
                  role="menuitem"
                  onClick={() => changeLang(lng)}
                  className="flex w-full items-center justify-between px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <span>{t(`topbar.languages.${lng}`)}</span>
                  {currentLang === lng && <Check size={14} className="text-brand-600" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-100"
          >
            <div className="h-8 w-8 rounded-full bg-brand-500 text-white text-xs font-semibold flex items-center justify-center">
              {(user?.full_name ?? 'U').split(' ').map((w) => w[0]).slice(0, 2).join('')}
            </div>
            <div className="text-left hidden sm:block">
              <p className="text-sm font-medium text-slate-900 leading-tight">{user?.full_name}</p>
              <p className="text-xs text-slate-500 capitalize">{user?.role}</p>
            </div>
          </button>

          {open && (
            <div
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-40"
            />
          )}
          {open && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-slate-200 py-1 z-50">
              <div className="px-3 py-2 border-b border-slate-100">
                <p className="text-sm font-medium">{user?.full_name}</p>
                <p className="text-xs text-slate-500 truncate">{user?.email}</p>
              </div>
              <button className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                <UserIcon size={16} /> {t('topbar.profile')}
              </button>
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
              >
                <LogOut size={16} /> {t('topbar.signOut')}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
