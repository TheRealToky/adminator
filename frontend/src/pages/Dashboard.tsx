import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  TrendingUp, Wallet, ShoppingCart, Receipt, AlertTriangle, Boxes, Factory,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { analytics } from '@/api/endpoints';
import { formatMoney, formatNumber, formatDate } from '@/lib/format';
import { PageHeader } from '@/components/ui/PageHeader';
import { KpiCard } from '@/components/dashboard/KpiCard';

const PIE_COLORS = ['#ea580c', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899'];

export function Dashboard() {
  const { t } = useTranslation();
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', days],
    queryFn: () => analytics.dashboard(days),
  });

  const ranges = [
    { value: 7, label: t('dashboard.ranges.last7') },
    { value: 30, label: t('dashboard.ranges.last30') },
    { value: 90, label: t('dashboard.ranges.last90') },
  ];

  const overdueCount = data?.invoices.by_status.find((s) => s.status === 'overdue')?.count ?? 0;

  return (
    <>
      <PageHeader
        title={t('dashboard.title')}
        subtitle={t('dashboard.subtitle')}
        actions={
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="input w-auto"
          >
            {ranges.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <KpiCard
          label={t('dashboard.kpi.revenue')}
          value={formatMoney(data?.kpis.revenue ?? 0)}
          changePct={data?.kpis.revenue_change_pct ?? null}
          hint={t('dashboard.kpi.vsPrev')}
          icon={TrendingUp}
          accent="brand"
        />
        <KpiCard
          label={t('dashboard.kpi.netProfit')}
          value={formatMoney(data?.kpis.net_profit ?? 0)}
          hint={t('dashboard.kpi.cogsOpex', {
            cogs: formatMoney(data?.kpis.cost_of_goods ?? 0),
            opex: formatMoney(data?.kpis.operating_expenses ?? 0),
          })}
          icon={Wallet}
          accent="green"
        />
        <KpiCard
          label={t('dashboard.kpi.receipts')}
          value={formatNumber(data?.kpis.receipts ?? 0)}
          hint={t('dashboard.kpi.avgTicket', { value: formatMoney(data?.kpis.average_ticket ?? 0) })}
          icon={ShoppingCart}
          accent="blue"
        />
        <KpiCard
          label={t('dashboard.kpi.inventoryOnHand')}
          value={formatMoney(data?.inventory.total_value ?? 0)}
          hint={t('dashboard.kpi.finishedRaw', {
            finished: formatMoney(data?.inventory.finished_goods_value ?? 0),
            raw: formatMoney(data?.inventory.raw_materials_value ?? 0),
          })}
          icon={Boxes}
          accent="purple"
        />
        <KpiCard
          label={t('dashboard.kpi.overdueInvoices')}
          value={formatMoney(data?.invoices.overdue_total ?? 0)}
          hint={t('dashboard.kpi.invoicesCount', { count: overdueCount })}
          icon={Receipt}
          accent="amber"
        />
      </div>

      {/* Revenue + profit timeseries */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
        <div className="card lg:col-span-2">
          <div className="card-header">
            <h3 className="font-semibold">{t('dashboard.revenueProfit')}</h3>
            <span className="text-xs text-slate-500">{t('dashboard.days', { count: days })}</span>
          </div>
          <div className="card-body">
            <div className="h-72">
              <ResponsiveContainer>
                <AreaChart data={data?.sales_timeseries ?? []}>
                  <defs>
                    <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ea580c" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#ea580c" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="profitFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="day"
                    tickFormatter={(d) => formatDate(d, { day: '2-digit', month: 'short' })}
                    tick={{ fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis tickFormatter={(v) => formatNumber(v)} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <Tooltip
                    formatter={(v: number) => formatMoney(v)}
                    labelFormatter={(d) => formatDate(d)}
                    contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }}
                  />
                  <Legend />
                  <Area
                    type="monotone" dataKey="revenue" stroke="#ea580c" fill="url(#revFill)"
                    strokeWidth={2} name={t('dashboard.revenueLabel')}
                  />
                  <Area
                    type="monotone" dataKey="profit" stroke="#10b981" fill="url(#profitFill)"
                    strokeWidth={2} name={t('dashboard.profitLabel')}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Payment mix */}
        <div className="card">
          <div className="card-header">
            <h3 className="font-semibold">{t('dashboard.paymentMix')}</h3>
          </div>
          <div className="card-body">
            <div className="h-72">
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={data?.payment_mix ?? []}
                    dataKey="revenue"
                    nameKey="method"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {(data?.payment_mix ?? []).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatMoney(v)} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      {/* Busy hours + Top products */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <div className="card">
          <div className="card-header">
            <h3 className="font-semibold">{t('dashboard.busyHours')}</h3>
            <span className="text-xs text-slate-500">{t('dashboard.busyHoursHint')}</span>
          </div>
          <div className="card-body">
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={data?.busy_hours ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
                  <Tooltip formatter={(v: number, n) => (n === 'receipts' ? formatNumber(v) : formatMoney(v))} />
                  <Bar dataKey="receipts" fill="#3b82f6" name={t('dashboard.receiptsLabel')} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="font-semibold">{t('dashboard.topProducts')}</h3>
            <span className="text-xs text-slate-500">{t('dashboard.byRevenue')}</span>
          </div>
          <div className="card-body">
            {isLoading ? (
              <div className="text-slate-400 text-sm py-8 text-center">{t('common.loading')}</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {(data?.top_products ?? []).map((p, idx) => (
                  <li key={p.product_id} className="py-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="h-7 w-7 rounded-md bg-brand-50 text-brand-600 text-xs font-semibold flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-slate-900">{p.name}</p>
                        <p className="text-xs text-slate-500">
                          {formatNumber(p.quantity)} {t('dashboard.soldSuffix')}
                        </p>
                      </div>
                    </div>
                    <span className="text-sm font-semibold text-slate-900">
                      {formatMoney(p.revenue)}
                    </span>
                  </li>
                ))}
                {(data?.top_products ?? []).length === 0 && (
                  <li className="py-8 text-center text-slate-400 text-sm">{t('dashboard.noData')}</li>
                )}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Stock + production */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
        <div className="card">
          <div className="card-header">
            <h3 className="font-semibold flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-500" /> {t('dashboard.lowStock')}
            </h3>
            <span className="text-xs text-slate-500">
              {t('dashboard.lowStockOf', {
                low: data?.stock_health.low_stock_count ?? 0,
                total: data?.stock_health.total_items ?? 0,
              })}
            </span>
          </div>
          <div className="card-body">
            <ul className="divide-y divide-slate-100">
              {(data?.stock_health.lowest_items ?? []).map((s) => (
                <li key={s.id} className="py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Boxes size={14} className="text-slate-400" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">{s.name}</p>
                      <p className="text-xs text-slate-500">
                        {s.kind === 'product' ? t('dashboard.kindProduct') : t('dashboard.kindRawMaterial')}
                      </p>
                    </div>
                  </div>
                  <span className="badge-red">
                    {formatNumber(s.quantity, 1)} {s.unit}
                  </span>
                </li>
              ))}
              {(data?.stock_health.lowest_items ?? []).length === 0 && (
                <li className="py-8 text-center text-slate-400 text-sm">{t('dashboard.stocksHealthy')}</li>
              )}
            </ul>
          </div>
        </div>

        <div className="card lg:col-span-2">
          <div className="card-header">
            <h3 className="font-semibold flex items-center gap-2">
              <Factory size={16} className="text-brand-500" /> {t('dashboard.productionByDay')}
            </h3>
            <span className="text-xs text-slate-500">
              {t('dashboard.productionSummary', {
                units: formatNumber(data?.production_summary.units_produced ?? 0),
                cost: formatMoney(data?.production_summary.total_cost ?? 0),
              })}
            </span>
          </div>
          <div className="card-body">
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={data?.production_summary.by_day ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="day"
                    tickFormatter={(d) => formatDate(d, { day: '2-digit', month: 'short' })}
                    tick={{ fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
                  <Tooltip
                    formatter={(v: number, n) => (n === 'units' ? formatNumber(v) : formatMoney(v))}
                    labelFormatter={(d) => formatDate(d)}
                  />
                  <Legend />
                  <Bar dataKey="units" fill="#ea580c" name={t('dashboard.unitsLabel')} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      {/* Expense breakdown */}
      <div className="card mt-6">
        <div className="card-header">
          <h3 className="font-semibold">{t('dashboard.expensesByCategory')}</h3>
        </div>
        <div className="card-body">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart layout="vertical" data={data?.expense_breakdown ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tickFormatter={(v) => formatNumber(v)} tick={{ fontSize: 12, fill: '#64748b' }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 12, fill: '#64748b' }} />
                <Tooltip formatter={(v: number) => formatMoney(v)} />
                <Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </>
  );
}
