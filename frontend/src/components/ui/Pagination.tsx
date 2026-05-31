import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: Props) {
  const { t } = useTranslation();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm text-slate-600">
      <p>
        <Trans
          i18nKey="common.pagination.showing"
          values={{ from, to, total }}
          components={{ 1: <span className="font-medium" /> }}
        />
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page === 1}
          className="btn-secondary px-2 py-1"
          aria-label={t('common.previousPage')}
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-slate-700">
          <Trans
            i18nKey="common.pagination.page"
            values={{ page, totalPages }}
            components={{ 1: <strong /> }}
          />
        </span>
        <button
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="btn-secondary px-2 py-1"
          aria-label={t('common.nextPage')}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
