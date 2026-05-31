import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Loader2 } from 'lucide-react';
export function DataTable({ columns, data, loading, empty, rowKey, onRowClick }) {
    if (loading && !data) {
        return (_jsxs("div", { className: "flex items-center justify-center py-16 text-slate-400", children: [_jsx(Loader2, { className: "animate-spin mr-2", size: 18 }), "Loading\u2026"] }));
    }
    if (!data || data.length === 0) {
        return _jsx("div", { className: "py-12", children: empty });
    }
    const align = (a) => (a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left');
    return (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "table-base", children: [_jsx("thead", { children: _jsx("tr", { children: columns.map((c) => (_jsx("th", { className: align(c.align), style: { width: c.width }, children: c.header }, c.key))) }) }), _jsx("tbody", { children: data.map((row) => (_jsx("tr", { className: onRowClick ? 'cursor-pointer' : '', onClick: () => onRowClick?.(row), children: columns.map((c) => (_jsx("td", { className: align(c.align), children: c.render(row) }, c.key))) }, rowKey(row)))) })] }) }));
}
