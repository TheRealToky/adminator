import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { ChevronLeft, ChevronRight } from 'lucide-react';
export function Pagination({ page, pageSize, total, onChange }) {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const to = Math.min(page * pageSize, total);
    return (_jsxs("div", { className: "flex items-center justify-between px-4 py-3 text-sm text-slate-600", children: [_jsxs("p", { children: ["Showing ", _jsx("span", { className: "font-medium", children: from }), "\u2013", _jsx("span", { className: "font-medium", children: to }), " of", ' ', _jsx("span", { className: "font-medium", children: total })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { onClick: () => onChange(Math.max(1, page - 1)), disabled: page === 1, className: "btn-secondary px-2 py-1", "aria-label": "Previous page", children: _jsx(ChevronLeft, { size: 16 }) }), _jsxs("span", { className: "text-slate-700", children: ["Page ", _jsx("strong", { children: page }), " of ", totalPages] }), _jsx("button", { onClick: () => onChange(Math.min(totalPages, page + 1)), disabled: page === totalPages, className: "btn-secondary px-2 py-1", "aria-label": "Next page", children: _jsx(ChevronRight, { size: 16 }) })] })] }));
}
