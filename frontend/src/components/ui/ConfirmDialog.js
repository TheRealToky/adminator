import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useTranslation } from 'react-i18next';
import { Modal } from './Modal';
export function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel, loading, destructive = true, }) {
    const { t } = useTranslation();
    return (_jsx(Modal, { open: open, onClose: onClose, title: title ?? t('common.areYouSure'), size: "sm", footer: _jsxs(_Fragment, { children: [_jsx("button", { onClick: onClose, className: "btn-secondary", disabled: loading, children: t('common.cancel') }), _jsx("button", { onClick: onConfirm, className: destructive ? 'btn-danger' : 'btn-primary', disabled: loading, children: loading ? t('common.working') : (confirmLabel ?? t('common.confirm')) })] }), children: _jsx("p", { className: "text-sm text-slate-600", children: message }) }));
}
