import type { LucideIcon } from 'lucide-react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

import { cn } from '@/lib/cn';

interface Props {
  label: string;
  value: string;
  changePct?: number | null;
  hint?: string;
  icon: LucideIcon;
  accent?: 'brand' | 'green' | 'blue' | 'amber' | 'red' | 'purple';
}

const accents = {
  brand:  'bg-brand-50 text-brand-600',
  green:  'bg-emerald-50 text-emerald-600',
  blue:   'bg-blue-50 text-blue-600',
  amber:  'bg-amber-50 text-amber-600',
  red:    'bg-red-50 text-red-600',
  purple: 'bg-purple-50 text-purple-600',
};

export function KpiCard({ label, value, changePct, hint, icon: Icon, accent = 'brand' }: Props) {
  const positive = (changePct ?? 0) >= 0;
  return (
    <div className="card card-body">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
        </div>
        <div className={cn('h-10 w-10 rounded-lg flex items-center justify-center', accents[accent])}>
          <Icon size={20} />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs">
        {typeof changePct === 'number' && (
          <span
            className={cn(
              'inline-flex items-center gap-0.5 font-medium',
              positive ? 'text-emerald-600' : 'text-red-600',
            )}
          >
            {positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            {Math.abs(changePct).toFixed(1)}%
          </span>
        )}
        {hint && <span className="text-slate-400">{hint}</span>}
      </div>
    </div>
  );
}
