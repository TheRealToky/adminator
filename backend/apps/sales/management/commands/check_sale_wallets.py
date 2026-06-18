"""Audit that each sale's payment method landed in the right kind of wallet.

Business rule we check (scoped to two methods for now):

    Mobile Money payment  ->  wallet.account_type == "mobile_money"
    Card payment          ->  wallet.account_type == "bank"

A sale is flagged when it has no wallet linked, or its wallet is of the
wrong account type. Cash / bank-transfer / credit sales are ignored here.

The audit always runs over a *precise* time window on ``occurred_at``,
treated as the half-open interval [start, end): start is included, end is
excluded. Naive inputs are interpreted in the project timezone
(BUSINESS_TIMEZONE, e.g. Africa/Kigali).

Examples
--------
    python manage.py check_sale_wallets --start 2026-03-01 --end 2026-06-16
    python manage.py check_sale_wallets --start "2026-06-15 08:00" --end "2026-06-15 20:00"
    python manage.py check_sale_wallets --last-days 30
    python manage.py check_sale_wallets --start 2026-01-01 --end 2026-07-01 --method card --show-ok

Exit status is 1 when any mismatch is found (0 otherwise), so it can be
wired into a cron job or CI check.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.finance.models import WalletAccountType
from apps.sales.models import PaymentMethod, Sale

# The rule under audit: payment method -> the wallet account_type it should
# settle into. Deliberately limited to the two methods asked for; extend this
# dict to cover cash / bank_transfer later.
EXPECTED_WALLET_TYPE = {
    PaymentMethod.MOBILE_MONEY: WalletAccountType.MOBILE_MONEY,
    PaymentMethod.CARD: WalletAccountType.BANK,
}


class Command(BaseCommand):
    help = (
        "Check that mobile-money and card sales are linked to the right wallet "
        "type (mobile_money / bank) within a precise occurred_at time window."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            help="Window start (inclusive). 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]'.",
        )
        parser.add_argument(
            "--end",
            help="Window end (exclusive). 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]'.",
        )
        parser.add_argument(
            "--last-days",
            type=int,
            help="Convenience: audit the last N days up to now (ignored if --start/--end given).",
        )
        parser.add_argument(
            "--method",
            choices=[PaymentMethod.MOBILE_MONEY, PaymentMethod.CARD],
            help="Only audit this one payment method (default: both).",
        )
        parser.add_argument(
            "--show-ok",
            action="store_true",
            help="Also list the sales that pass the check.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Max detail rows to print per section (0 = no limit). Default 100.",
        )

    # ── argument parsing ────────────────────────────────────────────────
    def _parse_bound(self, value: str, *, label: str) -> datetime:
        dt = parse_datetime(value)
        if dt is None:
            d = parse_date(value)
            if d is None:
                raise CommandError(
                    f"Could not parse --{label} '{value}'. "
                    "Use 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]'."
                )
            dt = datetime(d.year, d.month, d.day)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _resolve_window(self, options) -> tuple[datetime, datetime]:
        start_opt, end_opt, last_days = (
            options.get("start"),
            options.get("end"),
            options.get("last_days"),
        )
        if start_opt or end_opt:
            if not (start_opt and end_opt):
                raise CommandError("Provide both --start and --end (or use --last-days).")
            start = self._parse_bound(start_opt, label="start")
            end = self._parse_bound(end_opt, label="end")
        elif last_days is not None:
            if last_days <= 0:
                raise CommandError("--last-days must be a positive integer.")
            end = timezone.now()
            start = end - timedelta(days=last_days)
        else:
            raise CommandError("Specify the time window: --start/--end, or --last-days N.")

        if end <= start:
            raise CommandError("--end must be after --start.")
        return start, end

    # ── main ────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        start, end = self._resolve_window(options)
        methods = [options["method"]] if options.get("method") else list(EXPECTED_WALLET_TYPE)
        limit = options["limit"]

        tz = timezone.get_current_timezone()
        fmt = lambda dt: timezone.localtime(dt, tz).strftime("%Y-%m-%d %H:%M")  # noqa: E731

        self.stdout.write("Sale → wallet payment-method audit")
        self.stdout.write(
            f"Window : {fmt(start)} → {fmt(end)}  [{tz}]  (half-open: start included, end excluded)"
        )
        self.stdout.write(
            "Rule   : "
            + "  ·  ".join(
                f"{PaymentMethod(m).label} → {WalletAccountType(EXPECTED_WALLET_TYPE[m]).label} wallet"
                for m in methods
            )
        )
        self.stdout.write("")

        sales = (
            Sale.objects.filter(
                occurred_at__gte=start,
                occurred_at__lt=end,
                payment_method__in=methods,
            )
            .select_related("wallet")
            .order_by("occurred_at")
        )

        stats = {m: {"checked": 0, "ok": 0, "bad": 0} for m in methods}
        mismatches: list[tuple[Sale, str]] = []
        passing: list[Sale] = []

        for sale in sales.iterator():
            expected = EXPECTED_WALLET_TYPE[sale.payment_method]
            stats[sale.payment_method]["checked"] += 1

            wallet = sale.wallet
            if wallet is None:
                reason = "no wallet linked"
            elif wallet.account_type != expected:
                reason = (
                    f"linked to '{wallet.name}' [{wallet.account_type}], "
                    f"expected [{expected}]"
                )
            else:
                stats[sale.payment_method]["ok"] += 1
                passing.append(sale)
                continue

            stats[sale.payment_method]["bad"] += 1
            mismatches.append((sale, reason))

        self._print_summary(stats)

        if options["show_ok"]:
            self._print_rows("Passing sales", passing, fmt, limit)
        self._print_mismatch_rows(mismatches, fmt, limit)

        total_bad = sum(s["bad"] for s in stats.values())
        if total_bad:
            self.stdout.write(
                self.style.ERROR(f"\n✗ {total_bad} sale(s) point at the wrong wallet.")
            )
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("\n✓ Every audited sale is in the right wallet."))

    # ── output helpers ──────────────────────────────────────────────────
    def _print_summary(self, stats: dict) -> None:
        self.stdout.write("Summary")
        self.stdout.write(f"  {'method':<14}{'checked':>9}{'ok':>7}{'mismatch':>11}")
        total = {"checked": 0, "ok": 0, "bad": 0}
        for method, s in stats.items():
            for k in total:
                total[k] += s[k]
            line = f"  {method:<14}{s['checked']:>9}{s['ok']:>7}{s['bad']:>11}"
            self.stdout.write(self.style.ERROR(line) if s["bad"] else line)
        self.stdout.write(f"  {'-' * 39}")
        self.stdout.write(
            f"  {'TOTAL':<14}{total['checked']:>9}{total['ok']:>7}{total['bad']:>11}"
        )

    def _print_mismatch_rows(self, mismatches: list, fmt, limit: int) -> None:
        if not mismatches:
            return
        self.stdout.write(self.style.ERROR(f"\nMismatches ({len(mismatches)})"))
        header = f"  {'RECEIPT':<18}{'OCCURRED':<18}{'METHOD':<14}{'TOTAL':>13}  ISSUE"
        self.stdout.write(header)
        rows = mismatches if limit == 0 else mismatches[:limit]
        for sale, reason in rows:
            self.stdout.write(
                f"  {sale.receipt_number:<18}{fmt(sale.occurred_at):<18}"
                f"{sale.payment_method:<14}{sale.total:>13,.2f}  {reason}"
            )
        if limit and len(mismatches) > limit:
            self.stdout.write(f"  … {len(mismatches) - limit} more (raise --limit to see all)")

    def _print_rows(self, title: str, sales: list, fmt, limit: int) -> None:
        if not sales:
            return
        self.stdout.write(f"\n{title} ({len(sales)})")
        header = f"  {'RECEIPT':<18}{'OCCURRED':<18}{'METHOD':<14}{'TOTAL':>13}  WALLET"
        self.stdout.write(header)
        rows = sales if limit == 0 else sales[:limit]
        for sale in rows:
            wallet = f"{sale.wallet.name} [{sale.wallet.account_type}]" if sale.wallet else "—"
            self.stdout.write(
                f"  {sale.receipt_number:<18}{fmt(sale.occurred_at):<18}"
                f"{sale.payment_method:<14}{sale.total:>13,.2f}  {wallet}"
            )
        if limit and len(sales) > limit:
            self.stdout.write(f"  … {len(sales) - limit} more (raise --limit to see all)")
