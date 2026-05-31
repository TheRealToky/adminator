import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
export function SearchBar({ value, onChange, placeholder }) {
    const { t } = useTranslation();
    return (_jsxs("div", { className: "relative", children: [_jsx(Search, { size: 16, className: "absolute left-3 top-2.5 text-slate-400" }), _jsx("input", { value: value, onChange: (e) => onChange(e.target.value), placeholder: placeholder ?? t('common.search'), className: "input pl-9 pr-9 w-64" }), value && (_jsx("button", { onClick: () => onChange(''), className: "absolute right-2 top-2 text-slate-400 hover:text-slate-600", "aria-label": t('common.searchClear'), children: _jsx(X, { size: 16 }) }))] }));
}
