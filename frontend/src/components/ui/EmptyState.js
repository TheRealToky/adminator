import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function EmptyState({ icon: Icon, title, description, action }) {
    return (_jsxs("div", { className: "text-center py-12", children: [Icon && (_jsx("div", { className: "mx-auto h-12 w-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-4", children: _jsx(Icon, { size: 22 }) })), _jsx("p", { className: "text-base font-medium text-slate-900", children: title }), description && (_jsx("p", { className: "mt-1 text-sm text-slate-500 max-w-md mx-auto", children: description })), action && _jsx("div", { className: "mt-5 flex justify-center", children: action })] }));
}
