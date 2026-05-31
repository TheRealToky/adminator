import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { X } from 'lucide-react';
const sizes = {
    sm: 'max-w-md',
    md: 'max-w-xl',
    lg: 'max-w-3xl',
    xl: 'max-w-5xl',
};
export function Modal({ open, onClose, title, children, size = 'md', footer }) {
    useEffect(() => {
        if (!open)
            return;
        function onKey(e) {
            if (e.key === 'Escape')
                onClose();
        }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);
    if (!open)
        return null;
    return (_jsxs("div", { className: "fixed inset-0 z-50 flex items-center justify-center p-4", children: [_jsx("div", { className: "absolute inset-0 bg-slate-900/50", onClick: onClose }), _jsxs("div", { className: `relative w-full ${sizes[size]} bg-white rounded-xl shadow-xl border border-slate-200`, children: [_jsxs("div", { className: "flex items-center justify-between px-6 py-4 border-b border-slate-200", children: [_jsx("h2", { className: "text-lg font-semibold text-slate-900", children: title }), _jsx("button", { onClick: onClose, className: "text-slate-400 hover:text-slate-600 transition", children: _jsx(X, { size: 20 }) })] }), _jsx("div", { className: "p-6 max-h-[70vh] overflow-y-auto", children: children }), footer && (_jsx("div", { className: "px-6 py-4 border-t border-slate-200 bg-slate-50 rounded-b-xl flex justify-end gap-2", children: footer }))] })] }));
}
