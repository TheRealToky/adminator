import { Search, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function SearchBar({ value, onChange, placeholder }: Props) {
  const { t } = useTranslation();
  return (
    <div className="relative">
      <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? t('common.search')}
        className="input pl-9 pr-9 w-64"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
          aria-label={t('common.searchClear')}
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
