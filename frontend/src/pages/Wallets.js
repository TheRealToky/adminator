import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Wallet as WalletIcon, ArrowDownToLine, ArrowUpFromLine, ArrowLeftRight, History, } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { finance } from '@/api/endpoints';
import { extractErrorMessage } from '@/api/client';
import { useCrudList } from '@/hooks/useCrudList';
import { PageHeader } from '@/components/ui/PageHeader';
import { SearchBar } from '@/components/ui/SearchBar';
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ExportMenu } from '@/components/ui/ExportMenu';
import { fetchAllPaginated } from '@/lib/export';
import { formatDate, formatMoney } from '@/lib/format';
const ACCOUNT_TYPE_KEYS = [
    'cash',
    'mobile_money',
    'bank',
    'card',
    'other',
];
const today = () => new Date().toISOString().slice(0, 10);
const emptyForm = {
    name: '',
    account_type: 'cash',
    opening_balance: '0',
    institution: '',
    account_number: '',
    is_active: true,
    notes: '',
};
const emptyMovement = {
    amount: '0',
    occurred_on: today(),
    description: '',
    reference: '',
};
export function WalletsPage() {
    const qc = useQueryClient();
    const { t } = useTranslation();
    const list = useCrudList({
        queryKey: ['wallets'],
        fetcher: (p) => finance.wallets.list(p),
        deleter: (id) => finance.wallets.remove(id),
    });
    // All wallets (unpaginated) — powers the totals header and transfer targets.
    const allWallets = useQuery({
        queryKey: ['wallets-all'],
        queryFn: () => finance.wallets.list({ page_size: 200 }),
    });
    const wallets = allWallets.data?.results ?? [];
    const activeWallets = wallets.filter((w) => w.is_active);
    const totalHoldings = activeWallets.reduce((sum, w) => sum + Number(w.current_balance), 0);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm);
    const [toDelete, setToDelete] = useState(null);
    const [movement, setMovement] = useState({
        open: false, mode: 'deposit', wallet: null,
    });
    const [movementForm, setMovementForm] = useState(emptyMovement);
    const [transfer, setTransfer] = useState({
        open: false, wallet: null,
    });
    const [transferForm, setTransferForm] = useState({
        ...emptyMovement, destination: '',
    });
    const [entriesFor, setEntriesFor] = useState(null);
    function invalidateAll() {
        qc.invalidateQueries({ queryKey: ['wallets'] });
        qc.invalidateQueries({ queryKey: ['wallets-all'] });
        qc.invalidateQueries({ queryKey: ['wallet-entries'] });
    }
    const save = useMutation({
        mutationFn: () => editing ? finance.wallets.update(editing.id, form) : finance.wallets.create(form),
        onSuccess: () => {
            toast.success(editing ? t('wallets.updated') : t('wallets.created'));
            invalidateAll();
            setOpen(false);
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const recordMovement = useMutation({
        mutationFn: () => {
            const w = movement.wallet;
            const payload = {
                amount: Number(movementForm.amount),
                occurred_on: movementForm.occurred_on || undefined,
                description: movementForm.description || undefined,
                reference: movementForm.reference || undefined,
            };
            return movement.mode === 'deposit'
                ? finance.wallets.deposit(w.id, payload)
                : finance.wallets.withdraw(w.id, payload);
        },
        onSuccess: () => {
            toast.success(movement.mode === 'deposit' ? t('wallets.deposited') : t('wallets.withdrew'));
            invalidateAll();
            setMovement((m) => ({ ...m, open: false }));
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    const recordTransfer = useMutation({
        mutationFn: () => finance.wallets.transfer(transfer.wallet.id, {
            destination: transferForm.destination,
            amount: Number(transferForm.amount),
            occurred_on: transferForm.occurred_on || undefined,
            description: transferForm.description || undefined,
            reference: transferForm.reference || undefined,
        }),
        onSuccess: () => {
            toast.success(t('wallets.transferred'));
            invalidateAll();
            setTransfer((s) => ({ ...s, open: false }));
        },
        onError: (e) => toast.error(extractErrorMessage(e)),
    });
    function openCreate() {
        setEditing(null);
        setForm(emptyForm);
        setOpen(true);
    }
    function openEdit(row) {
        setEditing(row);
        setForm({
            name: row.name,
            account_type: row.account_type,
            opening_balance: row.opening_balance,
            institution: row.institution,
            account_number: row.account_number,
            is_active: row.is_active,
            notes: row.notes,
        });
        setOpen(true);
    }
    function openMovement(wallet, mode) {
        setMovement({ open: true, mode, wallet });
        setMovementForm({ ...emptyMovement });
    }
    function openTransfer(wallet) {
        setTransfer({ open: true, wallet });
        setTransferForm({ ...emptyMovement, destination: '' });
    }
    const columns = [
        {
            key: 'name',
            header: t('wallets.columns.name'),
            render: (r) => (_jsxs("div", { children: [_jsx("div", { className: "font-medium", children: r.name }), (r.institution || r.account_number) && (_jsx("div", { className: "text-xs text-slate-500", children: [r.institution, r.account_number].filter(Boolean).join(' · ') }))] })),
        },
        {
            key: 'type',
            header: t('wallets.columns.type'),
            render: (r) => (_jsx("span", { className: "badge-gray", children: t(`wallets.accountTypes.${r.account_type}`) })),
        },
        {
            key: 'opening',
            header: t('wallets.columns.opening'),
            align: 'right',
            render: (r) => formatMoney(r.opening_balance),
        },
        {
            key: 'balance',
            header: t('wallets.columns.balance'),
            align: 'right',
            render: (r) => (_jsx("span", { className: `font-semibold ${Number(r.current_balance) < 0 ? 'text-red-600' : 'text-slate-900'}`, children: formatMoney(r.current_balance) })),
        },
        {
            key: 'status',
            header: t('wallets.columns.status'),
            render: (r) => r.is_active ? (_jsx("span", { className: "badge-green", children: t('common.active') })) : (_jsx("span", { className: "badge-gray", children: t('common.off') })),
        },
        {
            key: 'actions',
            header: '',
            align: 'right',
            render: (r) => (_jsxs("div", { className: "flex justify-end gap-1", children: [_jsx("button", { className: "btn-ghost p-1.5 text-emerald-600", title: t('wallets.actions.deposit'), onClick: (e) => { e.stopPropagation(); openMovement(r, 'deposit'); }, children: _jsx(ArrowDownToLine, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-amber-600", title: t('wallets.actions.withdraw'), onClick: (e) => { e.stopPropagation(); openMovement(r, 'withdraw'); }, children: _jsx(ArrowUpFromLine, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", title: t('wallets.actions.transfer'), onClick: (e) => { e.stopPropagation(); openTransfer(r); }, children: _jsx(ArrowLeftRight, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", title: t('wallets.actions.history'), onClick: (e) => { e.stopPropagation(); setEntriesFor(r); }, children: _jsx(History, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5", onClick: (e) => { e.stopPropagation(); openEdit(r); }, children: _jsx(Pencil, { size: 14 }) }), _jsx("button", { className: "btn-ghost p-1.5 text-red-600", onClick: (e) => { e.stopPropagation(); setToDelete(r); }, children: _jsx(Trash2, { size: 14 }) })] })),
        },
    ];
    const exportColumns = [
        { key: 'name', header: t('wallets.exportCols.name'), value: (r) => r.name },
        {
            key: 'account_type',
            header: t('wallets.exportCols.type'),
            value: (r) => t(`wallets.accountTypes.${r.account_type}`),
        },
        { key: 'institution', header: t('wallets.exportCols.institution'), value: (r) => r.institution },
        { key: 'account_number', header: t('wallets.exportCols.accountNumber'), value: (r) => r.account_number },
        { key: 'opening_balance', header: t('wallets.exportCols.opening'), value: (r) => Number(r.opening_balance) },
        { key: 'current_balance', header: t('wallets.exportCols.balance'), value: (r) => Number(r.current_balance) },
        {
            key: 'is_active',
            header: t('wallets.exportCols.active'),
            value: (r) => (r.is_active ? t('common.yes') : t('common.no')),
        },
        { key: 'notes', header: t('wallets.exportCols.notes'), value: (r) => r.notes },
    ];
    const transferTargets = wallets.filter((w) => w.is_active && w.id !== transfer.wallet?.id);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: t('wallets.title'), subtitle: t('wallets.subtitle'), actions: _jsxs(_Fragment, { children: [_jsx(ExportMenu, { filename: "wallets", columns: exportColumns, fetchRows: () => fetchAllPaginated((p) => finance.wallets.list(p)) }), _jsxs("button", { onClick: openCreate, className: "btn-primary", children: [_jsx(Plus, { size: 16 }), " ", t('wallets.new')] })] }) }), _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4", children: [_jsxs("div", { className: "card p-4", children: [_jsx("div", { className: "text-xs uppercase tracking-wider font-semibold text-slate-400", children: t('wallets.totals.holdings') }), _jsx("div", { className: "mt-1 text-2xl font-bold text-slate-900", children: formatMoney(totalHoldings) })] }), _jsxs("div", { className: "card p-4", children: [_jsx("div", { className: "text-xs uppercase tracking-wider font-semibold text-slate-400", children: t('wallets.totals.activeAccounts') }), _jsx("div", { className: "mt-1 text-2xl font-bold text-slate-900", children: activeWallets.length })] }), _jsxs("div", { className: "card p-4", children: [_jsx("div", { className: "text-xs uppercase tracking-wider font-semibold text-slate-400", children: t('wallets.totals.totalAccounts') }), _jsx("div", { className: "mt-1 text-2xl font-bold text-slate-900", children: wallets.length })] })] }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "p-3 border-b border-slate-200", children: _jsx(SearchBar, { value: list.search, onChange: list.setSearch, placeholder: t('wallets.searchPlaceholder') }) }), _jsx(DataTable, { columns: columns, data: list.data?.results, loading: list.isLoading, rowKey: (r) => r.id, empty: _jsx(EmptyState, { icon: WalletIcon, title: t('wallets.emptyTitle'), description: t('wallets.emptyDescription') }) }), list.data && (_jsx(Pagination, { page: list.page, pageSize: list.pageSize, total: list.data.count, onChange: list.setPage }))] }), _jsx(Modal, { open: open, onClose: () => setOpen(false), title: editing ? t('wallets.editModal') : t('wallets.newModal'), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setOpen(false), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !form.name || save.isPending, onClick: () => save.mutate(), children: save.isPending ? t('common.saving') : t('common.save') })] }), children: _jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('wallets.fields.name') }), _jsx("input", { className: "input", value: form.name ?? '', onChange: (e) => setForm({ ...form, name: e.target.value }), placeholder: t('wallets.fields.namePlaceholder') })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('wallets.fields.accountType') }), _jsx("select", { className: "input", value: form.account_type ?? 'cash', onChange: (e) => setForm({ ...form, account_type: e.target.value }), children: ACCOUNT_TYPE_KEYS.map((k) => (_jsx("option", { value: k, children: t(`wallets.accountTypes.${k}`) }, k))) })] }), _jsxs("div", { children: [_jsxs("label", { className: "label", children: [t('wallets.fields.openingBalance'), editing && (_jsxs("span", { className: "text-slate-400", children: [" (", t('wallets.fields.openingLocked'), ")"] }))] }), _jsx("input", { type: "number", step: "0.01", className: "input", value: form.opening_balance ?? '0', onChange: (e) => setForm({ ...form, opening_balance: e.target.value }) })] }), _jsxs("div", { children: [_jsxs("label", { className: "label", children: [t('wallets.fields.institution'), ' ', _jsxs("span", { className: "text-slate-400", children: ["(", t('common.optional'), ")"] })] }), _jsx("input", { className: "input", value: form.institution ?? '', onChange: (e) => setForm({ ...form, institution: e.target.value }), placeholder: t('wallets.fields.institutionPlaceholder') })] }), _jsxs("div", { children: [_jsxs("label", { className: "label", children: [t('wallets.fields.accountNumber'), ' ', _jsxs("span", { className: "text-slate-400", children: ["(", t('common.optional'), ")"] })] }), _jsx("input", { className: "input", value: form.account_number ?? '', onChange: (e) => setForm({ ...form, account_number: e.target.value }), placeholder: t('wallets.fields.accountNumberPlaceholder') })] }), _jsx("div", { className: "sm:col-span-2", children: _jsxs("label", { className: "flex items-center gap-2 text-sm font-medium", children: [_jsx("input", { type: "checkbox", checked: form.is_active ?? true, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), t('wallets.fields.isActive')] }) }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('common.notes') }), _jsx("textarea", { className: "input", rows: 2, value: form.notes ?? '', onChange: (e) => setForm({ ...form, notes: e.target.value }) })] })] }) }), _jsx(Modal, { open: movement.open, onClose: () => setMovement((m) => ({ ...m, open: false })), title: movement.mode === 'deposit'
                    ? t('wallets.movement.depositTitle', { name: movement.wallet?.name ?? '' })
                    : t('wallets.movement.withdrawTitle', { name: movement.wallet?.name ?? '' }), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setMovement((m) => ({ ...m, open: false })), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !movementForm.amount ||
                                Number(movementForm.amount) <= 0 ||
                                recordMovement.isPending, onClick: () => recordMovement.mutate(), children: recordMovement.isPending ? t('common.saving') : t('common.save') })] }), children: _jsx(MovementFields, { form: movementForm, setForm: setMovementForm }) }), _jsx(Modal, { open: transfer.open, onClose: () => setTransfer((s) => ({ ...s, open: false })), title: t('wallets.transfer.title', { name: transfer.wallet?.name ?? '' }), footer: _jsxs(_Fragment, { children: [_jsx("button", { className: "btn-secondary", onClick: () => setTransfer((s) => ({ ...s, open: false })), children: t('common.cancel') }), _jsx("button", { className: "btn-primary", disabled: !transferForm.destination ||
                                !transferForm.amount ||
                                Number(transferForm.amount) <= 0 ||
                                recordTransfer.isPending, onClick: () => recordTransfer.mutate(), children: recordTransfer.isPending ? t('common.saving') : t('wallets.transfer.submit') })] }), children: _jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('wallets.transfer.destination') }), _jsxs("select", { className: "input", value: transferForm.destination, onChange: (e) => setTransferForm((f) => ({ ...f, destination: e.target.value })), children: [_jsx("option", { value: "", children: t('common.select') }), transferTargets.map((w) => (_jsxs("option", { value: w.id, children: [w.name, " \u2014 ", formatMoney(w.current_balance)] }, w.id)))] }), transferTargets.length === 0 && (_jsx("p", { className: "text-xs text-slate-500 mt-1", children: t('wallets.transfer.noTargets') }))] }), _jsx(MovementFields, { form: transferForm, setForm: (updater) => setTransferForm((f) => ({ ...f, ...updater(f) })) })] }) }), _jsx(Modal, { open: !!entriesFor, onClose: () => setEntriesFor(null), title: t('wallets.history.title', { name: entriesFor?.name ?? '' }), size: "lg", children: entriesFor && _jsx(EntriesList, { walletId: entriesFor.id }) }), _jsx(ConfirmDialog, { open: !!toDelete, onClose: () => setToDelete(null), title: t('wallets.deleteTitle'), message: t('wallets.deleteMessage', { name: toDelete?.name ?? '' }), confirmLabel: t('common.delete'), loading: list.deleteMutation.isPending, onConfirm: () => {
                    if (toDelete)
                        list.deleteMutation.mutate(toDelete.id, {
                            onSettled: () => {
                                setToDelete(null);
                                invalidateAll();
                            },
                        });
                } })] }));
}
// ── Shared amount/date/description fields ───────────────────────────────────
function MovementFields({ form, setForm, }) {
    const { t } = useTranslation();
    return (_jsxs("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "label", children: t('wallets.movement.amount') }), _jsx("input", { type: "number", step: "0.01", min: "0", className: "input", value: form.amount, onChange: (e) => setForm((f) => ({ ...f, amount: e.target.value })) })] }), _jsxs("div", { children: [_jsx("label", { className: "label", children: t('wallets.movement.date') }), _jsx("input", { type: "date", className: "input", value: form.occurred_on, onChange: (e) => setForm((f) => ({ ...f, occurred_on: e.target.value })) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('wallets.movement.description') }), _jsx("input", { className: "input", value: form.description, onChange: (e) => setForm((f) => ({ ...f, description: e.target.value })) })] }), _jsxs("div", { className: "sm:col-span-2", children: [_jsx("label", { className: "label", children: t('wallets.movement.reference') }), _jsx("input", { className: "input", value: form.reference, onChange: (e) => setForm((f) => ({ ...f, reference: e.target.value })) })] })] }));
}
// ── A wallet's unified activity: manual entries + linked flows ──────────────
const SOURCE_BADGE = {
    manual: 'badge-gray',
    sale: 'badge-green',
    transaction: 'badge-blue',
    expense: 'badge-gray',
};
function EntriesList({ walletId }) {
    const { t } = useTranslation();
    const query = useQuery({
        queryKey: ['wallet-ledger', walletId],
        queryFn: () => finance.wallets.ledger(walletId),
    });
    if (query.isLoading) {
        return _jsx("p", { className: "text-sm text-slate-500 py-6 text-center", children: t('common.loading') });
    }
    const rows = query.data ?? [];
    if (rows.length === 0) {
        return _jsx("p", { className: "text-sm text-slate-500 py-6 text-center", children: t('wallets.history.empty') });
    }
    return (_jsx("div", { className: "max-h-[60vh] overflow-y-auto -mx-1", children: _jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsxs("tr", { className: "text-left text-xs uppercase tracking-wider text-slate-400", children: [_jsx("th", { className: "py-2 px-1 font-semibold", children: t('wallets.history.date') }), _jsx("th", { className: "py-2 px-1 font-semibold", children: t('wallets.history.type') }), _jsx("th", { className: "py-2 px-1 font-semibold", children: t('wallets.history.description') }), _jsx("th", { className: "py-2 px-1 font-semibold text-right", children: t('wallets.history.amount') })] }) }), _jsx("tbody", { children: rows.map((r) => (_jsxs("tr", { className: "border-t border-slate-100", children: [_jsx("td", { className: "py-2 px-1 whitespace-nowrap", children: formatDate(r.occurred_on) }), _jsx("td", { className: "py-2 px-1", children: _jsx("span", { className: SOURCE_BADGE[r.source], children: r.kind_display }) }), _jsx("td", { className: "py-2 px-1", children: r.description || '—' }), _jsxs("td", { className: `py-2 px-1 text-right font-semibold ${r.direction === 'in' ? 'text-emerald-600' : 'text-slate-900'}`, children: [r.direction === 'in' ? '+' : '−', formatMoney(r.amount)] })] }, `${r.source}:${r.id}`))) })] }) }));
}
