const currencyCode = import.meta.env.VITE_BUSINESS_CURRENCY ?? 'RWF';
const currencySymbol = import.meta.env.VITE_BUSINESS_CURRENCY_SYMBOL ?? 'FRw';
const locale = import.meta.env.VITE_BUSINESS_LOCALE ?? 'en-RW';
export function formatMoney(amount) {
    if (amount === null || amount === undefined || amount === '')
        return '—';
    const value = typeof amount === 'string' ? Number(amount) : amount;
    if (Number.isNaN(value))
        return '—';
    try {
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currencyCode,
            maximumFractionDigits: 0,
        }).format(value);
    }
    catch {
        return `${currencySymbol} ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
}
export function formatNumber(value, digits = 0) {
    if (value === null || value === undefined || value === '')
        return '—';
    const num = typeof value === 'string' ? Number(value) : value;
    if (Number.isNaN(num))
        return '—';
    return new Intl.NumberFormat(locale, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits === 0 ? 0 : digits,
    }).format(num);
}
export function formatDate(input, options) {
    if (!input)
        return '—';
    const date = typeof input === 'string' ? new Date(input) : input;
    return new Intl.DateTimeFormat(locale, {
        year: 'numeric', month: 'short', day: '2-digit', ...options,
    }).format(date);
}
export function formatDateTime(input) {
    if (!input)
        return '—';
    const date = typeof input === 'string' ? new Date(input) : input;
    return new Intl.DateTimeFormat(locale, {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
    }).format(date);
}
export function formatPercent(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(value))
        return '—';
    return `${value.toFixed(digits)}%`;
}
