import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { cn } from '@/lib/cn';
const accents = {
    brand: 'bg-brand-50 text-brand-600',
    green: 'bg-emerald-50 text-emerald-600',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
};
export function KpiCard({ label, value, changePct, hint, icon: Icon, accent = 'brand' }) {
    const positive = (changePct ?? 0) >= 0;
    return (_jsxs("div", { className: "card card-body", children: [_jsxs("div", { className: "flex items-start justify-between", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm text-slate-500", children: label }), _jsx("p", { className: "mt-1 text-2xl font-semibold text-slate-900", children: value })] }), _jsx("div", { className: cn('h-10 w-10 rounded-lg flex items-center justify-center', accents[accent]), children: _jsx(Icon, { size: 20 }) })] }), _jsxs("div", { className: "mt-3 flex items-center gap-2 text-xs", children: [typeof changePct === 'number' && (_jsxs("span", { className: cn('inline-flex items-center gap-0.5 font-medium', positive ? 'text-emerald-600' : 'text-red-600'), children: [positive ? _jsx(ArrowUpRight, { size: 14 }) : _jsx(ArrowDownRight, { size: 14 }), Math.abs(changePct).toFixed(1), "%"] })), hint && _jsx("span", { className: "text-slate-400", children: hint })] })] }));
}
