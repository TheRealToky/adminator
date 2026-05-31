import { type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: 'left' | 'right' | 'center';
  width?: string;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[] | undefined;
  loading?: boolean;
  empty?: ReactNode;
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({ columns, data, loading, empty, rowKey, onRowClick }: Props<T>) {
  const { t } = useTranslation();
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400">
        <Loader2 className="animate-spin mr-2" size={18} />
        {t('common.loading')}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <div className="py-12">{empty}</div>;
  }

  const align = (a?: string) => (a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left');

  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={align(c.align)} style={{ width: c.width }}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? 'cursor-pointer' : ''}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((c) => (
                <td key={c.key} className={align(c.align)}>{c.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
