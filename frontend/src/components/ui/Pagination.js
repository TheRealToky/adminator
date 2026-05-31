import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';
export function Pagination({ page, pageSize, total, onChange }) {
    const { t } = useTranslation();
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const to = Math.min(page * pageSize, total);
    return (_jsxs("div", { className: "flex items-center justify-between px-4 py-3 text-sm text-slate-600", children: [_jsx("p", { children: _jsx(Trans, { i18nKey: "common.pagination.showing", values: { from, to, total }, components: { 1: _jsx("span", { className: "font-medium" }) } }) }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { onClick: () => onChange(Math.max(1, page - 1)), disabled: page === 1, className: "btn-secondary px-2 py-1", "aria-label": t('common.previousPage'), children: _jsx(ChevronLeft, { size: 16 }) }), _jsx("span", { className: "text-slate-700", children: _jsx(Trans, { i18nKey: "common.pagination.page", values: { page, totalPages }, components: { 1: _jsx("strong", {}) } }) }), _jsx("button", { onClick: () => onChange(Math.min(totalPages, page + 1)), disabled: page === totalPages, className: "btn-secondary px-2 py-1", "aria-label": t('common.nextPage'), children: _jsx(ChevronRight, { size: 16 }) })] })] }));
}
