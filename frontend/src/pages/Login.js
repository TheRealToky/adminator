import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
    const from = location.state?.from?.pathname ?? '/';
    async function onSubmit(e) {
        e.preventDefault();
        setSubmitting(true);
        try {
            await login(email, password);
            navigate(from, { replace: true });
        }
        catch (err) {
            toast.error(extractErrorMessage(err, t('login.invalidCredentials')));
        }
        finally {
            setSubmitting(false);
        }
    }
    return (_jsx("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-white to-amber-50 p-4", children: _jsxs("div", { className: "w-full max-w-md", children: [_jsxs("div", { className: "text-center mb-8", children: [_jsx("div", { className: "inline-flex h-14 w-14 rounded-2xl bg-brand-500 text-white items-center justify-center text-2xl font-bold mb-3", children: "A" }), _jsx("h1", { className: "text-2xl font-bold text-slate-900", children: t('common.appName') }), _jsx("p", { className: "text-sm text-slate-500 mt-1", children: t('login.subtitle') })] }), _jsxs("form", { onSubmit: onSubmit, className: "card card-body space-y-4", children: [_jsxs("div", { children: [_jsx("label", { htmlFor: "email", className: "label", children: t('common.email') }), _jsx("input", { id: "email", type: "email", required: true, value: email, onChange: (e) => setEmail(e.target.value), className: "input", autoComplete: "email" })] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "password", className: "label", children: t('login.password') }), _jsx("input", { id: "password", type: "password", required: true, value: password, onChange: (e) => setPassword(e.target.value), className: "input", autoComplete: "current-password" })] }), _jsx("button", { type: "submit", disabled: submitting, className: "btn-primary w-full", children: submitting ? (_jsxs(_Fragment, { children: [_jsx(Loader2, { className: "animate-spin mr-2", size: 16 }), " ", t('login.signingIn')] })) : t('login.signIn') }), _jsx("p", { className: "text-xs text-slate-500 text-center", children: t('login.demoSeed') })] })] }) }));
}
