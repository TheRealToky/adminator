import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { Modal } from './Modal';
export function ConfirmDialog({ open, onClose, onConfirm, title = 'Are you sure?', message, confirmLabel = 'Confirm', loading, destructive = true, }) {
    return (_jsx(Modal, { open: open, onClose: onClose, title: title, size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { onClick: onClose, className: "btn-secondary", disabled: loading, children: "Cancel" }), _jsx("button", { onClick: onConfirm, className: destructive ? 'btn-danger' : 'btn-primary', disabled: loading, children: loading ? 'Working...' : confirmLabel })] }), children: _jsx("p", { className: "text-sm text-slate-600", children: message }) }));
}
