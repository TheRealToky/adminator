import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function PageHeader({ title, subtitle, actions }) {
    return (_jsxs("div", { className: "flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-semibold text-slate-900", children: title }), subtitle && _jsx("p", { className: "mt-1 text-sm text-slate-500", children: subtitle })] }), actions && _jsx("div", { className: "flex items-center gap-2", children: actions })] }));
}
