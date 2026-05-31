import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { auth as authApi } from '@/api/endpoints';
import { tokens } from '@/api/client';
import type { User } from '@/api/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!tokens.getAccess()) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        tokens.clear();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    bootstrap();
    return () => { cancelled = true; };
  }, []);

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password);
    tokens.setTokens(res.access, res.refresh);
    setUser(res.user);
  }

  function logout() {
    tokens.clear();
    setUser(null);
    window.location.assign('/login');
  }

  async function refreshUser() {
    const me = await authApi.me();
    setUser(me);
  }

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
