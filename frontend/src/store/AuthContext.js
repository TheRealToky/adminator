import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useEffect, useState } from 'react';
import { auth as authApi } from '@/api/endpoints';
import { tokens } from '@/api/client';
const AuthContext = createContext(undefined);
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        let cancelled = false;
        async function bootstrap() {
            if (!tokens.getAccess()) {
                if (!cancelled)
                    setLoading(false);
                return;
            }
            try {
                const me = await authApi.me();
                if (!cancelled)
                    setUser(me);
            }
            catch {
                tokens.clear();
            }
            finally {
                if (!cancelled)
                    setLoading(false);
            }
        }
        bootstrap();
        return () => { cancelled = true; };
    }, []);
    async function login(email, password) {
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
    return (_jsx(AuthContext.Provider, { value: { user, loading, isAuthenticated: !!user, login, logout, refreshUser }, children: children }));
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error('useAuth must be used inside <AuthProvider>');
    return ctx;
}
