import { useEffect, useRef, useState } from 'react';
import { Download, FileSpreadsheet, FileText, Braces, Loader2, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';

import { extractErrorMessage } from '@/api/client';
import {
  exportRows,
  type ExportColumn,
  type ExportFormat,
} from '@/lib/export';

interface Props<T> {
  filename: string;
  columns: ExportColumn<T>[];
  fetchRows: () => Promise<T[]>;
  label?: string;
  size?: 'sm' | 'md';
  disabled?: boolean;
}

const FORMATS: Array<{
  key: ExportFormat;
  label: string;
  hint: string;
  icon: typeof FileSpreadsheet;
}> = [
  { key: 'xlsx', label: 'Excel (.xlsx)', hint: 'Spreadsheet', icon: FileSpreadsheet },
  { key: 'csv', label: 'CSV (.csv)', hint: 'Comma-separated', icon: FileText },
  { key: 'json', label: 'JSON (.json)', hint: 'Raw data', icon: Braces },
];

export function ExportMenu<T>({
  filename,
  columns,
  fetchRows,
  label = 'Export',
  size = 'md',
  disabled = false,
}: Props<T>) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function handlePick(format: ExportFormat) {
    if (busy) return;
    setBusy(format);
    setOpen(false);
    try {
      const rows = await fetchRows();
      if (rows.length === 0) {
        toast.message('Nothing to export', { description: 'There are no rows to include.' });
        return;
      }
      exportRows(rows, columns, format, filename);
      toast.success(`Exported ${rows.length} row${rows.length === 1 ? '' : 's'} as ${format.toUpperCase()}.`);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not export data.'));
    } finally {
      setBusy(null);
    }
  }

  const btnPadding = size === 'sm' ? 'px-2 py-1 text-xs' : '';
  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        className={`btn-secondary ${btnPadding}`}
        disabled={disabled || !!busy}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {busy ? <Loader2 size={iconSize} className="animate-spin" /> : <Download size={iconSize} />}
        {busy ? `Exporting ${busy.toUpperCase()}…` : label}
        <ChevronDown size={iconSize} className="opacity-60" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-slate-200 bg-white shadow-lg py-1"
        >
          {FORMATS.map(({ key, label: optLabel, hint, icon: Icon }) => (
            <button
              key={key}
              type="button"
              role="menuitem"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50"
              onClick={() => handlePick(key)}
            >
              <Icon size={16} className="text-slate-500" />
              <span className="flex-1">
                <span className="block font-medium text-slate-800">{optLabel}</span>
                <span className="block text-xs text-slate-500">{hint}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
