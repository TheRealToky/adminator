import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { Download, FileSpreadsheet, FileText, Braces, Loader2, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/store/AuthContext';
import { exportMultiSheet } from '@/lib/export';
import { buildExportDatasets } from '@/lib/exportDatasets';
const FORMAT_KEYS = ['xlsx', 'csv', 'json'];
const FORMAT_ICONS = {
    xlsx: FileSpreadsheet,
    csv: FileText,
    json: Braces,
};
/**
 * Global "Export all" action: bundles every table the user can see into a single
 * file (one xlsx with a sheet per table, one keyed json, or one sectioned csv).
 * Tables are fetched one at a time; a table that fails (e.g. permissions) is
 * skipped with a warning rather than aborting the whole export.
 */
export function ExportAllMenu({ size = 'md' }) {
    const { t } = useTranslation();
    const { user } = useAuth();
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(null);
    const [progress, setProgress] = useState(null);
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
        const datasets = buildExportDatasets(t, { includeUsers: user?.is_admin ?? false });
        setBusy(format);
        setOpen(false);
        setProgress({ done: 0, total: datasets.length });
        const sheets = [];
        let skipped = 0;
        try {
            for (const ds of datasets) {
                try {
                    const rows = await ds.fetchRows();
                    sheets.push({
                        key: ds.key,
                        sheetName: ds.title,
                        label: ds.title,
                        columns: ds.columns,
                        rows,
                    });
                }
                catch {
                    skipped += 1;
                    toast.warning(t('export.all.skipped', { name: ds.title }));
                }
                finally {
                    setProgress((p) => (p ? { ...p, done: p.done + 1 } : p));
                }
            }
            const totalRows = sheets.reduce((sum, s) => sum + s.rows.length, 0);
            if (totalRows === 0) {
                toast.message(t('export.nothingTitle'), { description: t('export.nothingDescription') });
                return;
            }
            exportMultiSheet(sheets, format, t('export.all.filename'));
            toast.success(t('export.all.success', {
                tables: sheets.length,
                rows: totalRows,
                format: format.toUpperCase(),
            }));
            if (skipped > 0) {
                toast.warning(t('export.all.partial', { count: skipped }));
            }
        }
        catch {
            toast.error(t('export.failed'));
        }
        finally {
            setBusy(null);
            setProgress(null);
        }
    }
    const btnPadding = size === 'sm' ? 'px-2 py-1 text-xs' : '';
    const iconSize = size === 'sm' ? 12 : 14;
    return (_jsxs("div", { ref: containerRef, className: "relative inline-block", children: [_jsxs("button", { type: "button", className: `btn-secondary ${btnPadding}`, disabled: !!busy, onClick: () => setOpen((v) => !v), "aria-haspopup": "menu", "aria-expanded": open, children: [busy ? _jsx(Loader2, { size: iconSize, className: "animate-spin" }) : _jsx(Download, { size: iconSize }), busy
                        ? progress
                            ? t('export.all.progress', {
                                format: busy.toUpperCase(),
                                done: progress.done,
                                total: progress.total,
                            })
                            : t('export.exporting', { format: busy.toUpperCase() })
                        : t('export.all.label'), _jsx(ChevronDown, { size: iconSize, className: "opacity-60" })] }), open && (_jsxs("div", { role: "menu", className: "absolute right-0 z-30 mt-1 w-64 rounded-md border border-slate-200 bg-white shadow-lg py-1", children: [_jsx("p", { className: "px-3 py-1.5 text-[11px] uppercase tracking-wider font-semibold text-slate-400", children: t('export.all.heading') }), FORMAT_KEYS.map((key) => {
                        const Icon = FORMAT_ICONS[key];
                        return (_jsxs("button", { type: "button", role: "menuitem", className: "w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50", onClick: () => handlePick(key), children: [_jsx(Icon, { size: 16, className: "text-slate-500" }), _jsxs("span", { className: "flex-1", children: [_jsx("span", { className: "block font-medium text-slate-800", children: t(`export.formats.${key}`) }), _jsx("span", { className: "block text-xs text-slate-500", children: t(`export.all.formatHints.${key}`) })] })] }, key));
                    })] }))] }));
}
