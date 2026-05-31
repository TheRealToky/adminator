import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { Download, FileSpreadsheet, FileText, Braces, Loader2, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { extractErrorMessage } from '@/api/client';
import { exportRows, } from '@/lib/export';
const FORMAT_KEYS = ['xlsx', 'csv', 'json'];
const FORMAT_ICONS = {
    xlsx: FileSpreadsheet,
    csv: FileText,
    json: Braces,
};
export function ExportMenu({ filename, columns, fetchRows, label, size = 'md', disabled = false, }) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(null);
    const containerRef = useRef(null);
    useEffect(() => {
        if (!open)
            return;
        function onDocClick(e) {
            if (!containerRef.current?.contains(e.target))
                setOpen(false);
        }
        function onKey(e) {
            if (e.key === 'Escape')
                setOpen(false);
        }
        document.addEventListener('mousedown', onDocClick);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDocClick);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);
    async function handlePick(format) {
        if (busy)
            return;
        setBusy(format);
        setOpen(false);
        try {
            const rows = await fetchRows();
            if (rows.length === 0) {
                toast.message(t('export.nothingTitle'), { description: t('export.nothingDescription') });
                return;
            }
            exportRows(rows, columns, format, filename);
            toast.success(t('export.successOther', {
                count: rows.length,
                format: format.toUpperCase(),
            }));
        }
        catch (err) {
            toast.error(extractErrorMessage(err, t('export.failed')));
        }
        finally {
            setBusy(null);
        }
    }
    const btnPadding = size === 'sm' ? 'px-2 py-1 text-xs' : '';
    const iconSize = size === 'sm' ? 12 : 14;
    const exportLabel = label ?? t('export.label');
    return (_jsxs("div", { ref: containerRef, className: "relative inline-block", children: [_jsxs("button", { type: "button", className: `btn-secondary ${btnPadding}`, disabled: disabled || !!busy, onClick: () => setOpen((v) => !v), "aria-haspopup": "menu", "aria-expanded": open, children: [busy ? _jsx(Loader2, { size: iconSize, className: "animate-spin" }) : _jsx(Download, { size: iconSize }), busy ? t('export.exporting', { format: busy.toUpperCase() }) : exportLabel, _jsx(ChevronDown, { size: iconSize, className: "opacity-60" })] }), open && (_jsx("div", { role: "menu", className: "absolute right-0 z-30 mt-1 w-56 rounded-md border border-slate-200 bg-white shadow-lg py-1", children: FORMAT_KEYS.map((key) => {
                    const Icon = FORMAT_ICONS[key];
                    return (_jsxs("button", { type: "button", role: "menuitem", className: "w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50", onClick: () => handlePick(key), children: [_jsx(Icon, { size: 16, className: "text-slate-500" }), _jsxs("span", { className: "flex-1", children: [_jsx("span", { className: "block font-medium text-slate-800", children: t(`export.formats.${key}`) }), _jsx("span", { className: "block text-xs text-slate-500", children: t(`export.formats.${key}Hint`) })] })] }, key));
                }) }))] }));
}
