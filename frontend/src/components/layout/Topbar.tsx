import { Menu, LogOut, User as UserIcon } from 'lucide-react';
import { useState } from 'react';

import { useAuth } from '@/store/AuthContext';

interface Props {
  onMenu: () => void;
}

export function Topbar({ onMenu }: Props) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-slate-200">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6">
        <button onClick={onMenu} className="lg:hidden text-slate-600">
          <Menu size={22} />
        </button>
        <div className="flex-1" />
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
                <UserIcon size={16} /> Profile
              </button>
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
              >
                <LogOut size={16} /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
