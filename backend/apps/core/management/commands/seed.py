"""
Seed the database with realistic demo data for a small bakery.

Usage:
    python manage.py seed                # always seed
    python manage.py seed --if-empty     # only seed when the DB is empty
    python manage.py seed --fresh        # wipe + reseed (DEV ONLY)
"""
from __future__ import annotations

import os
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    Product,
    ProductCategory,
    RawMaterial,
    RecipeItem,
    Supplier,
    UnitOfMeasure,
)
from apps.finance.models import Budget, Expense, ExpenseCategory, Invoice, InvoiceStatus
from apps.inventory import services as inventory_services
from apps.inventory.models import StockItem, StockMovement
from apps.production import services as production_services
from apps.production.models import ProductionRun
from apps.sales import services as sales_services
from apps.sales.models import PaymentMethod, Sale, SaleChannel
from apps.accounts.models import Role


User = get_user_model()
RNG = random.Random(42)  # reproducible seed


# ── Reference data ────────────────────────────────────────────────────────
CATEGORIES = [
    "Breads", "Pastries", "Cakes", "Cookies", "Beverages", "Sandwiches",
]

SUPPLIERS = [
    ("Kigali Mills", "Jean Baptiste", "+250 788 100 200", "orders@kgmills.rw"),
    ("Lakeside Dairy", "Aline Uwase", "+250 788 110 220", "sales@lakedairy.rw"),
    ("EquaFresh Eggs", "Patrick Habimana", "+250 788 120 240", "hello@equafresh.rw"),
    ("Sugar Plus Co.", "Marie Ingabire", "+250 788 130 260", "contact@sugarplus.rw"),
    ("Bakers Choice Imports", "Eric Niyonzima", "+250 788 140 280", "eric@bakerschoice.rw"),
]

RAW_MATERIALS = [
    # (sku, name, unit, unit_cost, reorder_threshold, supplier_idx)
    ("RM-FL-AP", "All-purpose flour", "g", "0.85", "25000", 0),
    ("RM-FL-WW", "Whole-wheat flour", "g", "0.95", "15000", 0),
    ("RM-FL-BR", "Bread flour", "g", "0.90", "20000", 0),
    ("RM-SG-WH", "White sugar", "g", "1.20", "10000", 3),
    ("RM-SG-BR", "Brown sugar", "g", "1.50", "5000", 3),
    ("RM-BU-UN", "Unsalted butter", "g", "8.50", "5000", 1),
    ("RM-EG-LG", "Eggs (large)", "unit", "120", "60", 2),
    ("RM-MK-WH", "Whole milk", "ml", "1.10", "10000", 1),
    ("RM-MK-CR", "Heavy cream", "ml", "3.20", "3000", 1),
    ("RM-YE-DR", "Dry yeast", "g", "5.00", "1000", 4),
    ("RM-SL-FI", "Fine salt", "g", "0.40", "2000", 3),
    ("RM-CH-DK", "Dark chocolate", "g", "12.00", "3000", 4),
    ("RM-CH-MK", "Milk chocolate", "g", "11.00", "3000", 4),
    ("RM-VA-EX", "Vanilla extract", "ml", "25.00", "500", 4),
    ("RM-CN-PD", "Cinnamon powder", "g", "9.00", "500", 4),
    ("RM-BP-PD", "Baking powder", "g", "3.50", "500", 3),
    ("RM-OL-VE", "Vegetable oil", "ml", "1.80", "3000", 3),
    ("RM-CF-GR", "Coffee beans (ground)", "g", "18.00", "1500", 4),
    ("RM-TE-LF", "Tea leaves", "g", "14.00", "500", 4),
    ("RM-FR-ST", "Fresh strawberries", "g", "6.50", "1000", 2),
]

PRODUCTS = [
    # (sku, name, category, unit, selling_price, reorder_threshold, recipe[(material_sku, qty)])
    ("PR-BG-CL", "Classic baguette", "Breads", "unit", "1200", 8,
     [("RM-FL-BR", 250), ("RM-YE-DR", 3), ("RM-SL-FI", 5), ("RM-OL-VE", 5)]),
    ("PR-BR-WW", "Whole-wheat loaf", "Breads", "unit", "1800", 6,
     [("RM-FL-WW", 350), ("RM-YE-DR", 4), ("RM-SL-FI", 6), ("RM-MK-WH", 50)]),
    ("PR-BR-MU", "Multigrain loaf", "Breads", "unit", "2000", 6,
     [("RM-FL-BR", 200), ("RM-FL-WW", 150), ("RM-YE-DR", 4), ("RM-SL-FI", 6)]),
    ("PR-BR-BR", "Brioche loaf", "Breads", "unit", "2800", 5,
     [("RM-FL-AP", 300), ("RM-BU-UN", 80), ("RM-EG-LG", 2), ("RM-SG-WH", 30), ("RM-YE-DR", 3)]),
    ("PR-BR-FB", "Focaccia", "Breads", "unit", "2400", 4,
     [("RM-FL-AP", 280), ("RM-OL-VE", 30), ("RM-SL-FI", 8), ("RM-YE-DR", 3)]),
    ("PR-CR-PL", "Plain croissant", "Pastries", "unit", "900", 12,
     [("RM-FL-AP", 80), ("RM-BU-UN", 50), ("RM-MK-WH", 20), ("RM-SG-WH", 8), ("RM-YE-DR", 1)]),
    ("PR-CR-CH", "Chocolate croissant", "Pastries", "unit", "1200", 10,
     [("RM-FL-AP", 80), ("RM-BU-UN", 50), ("RM-MK-WH", 20), ("RM-CH-DK", 25), ("RM-YE-DR", 1)]),
    ("PR-CR-AL", "Almond croissant", "Pastries", "unit", "1400", 8,
     [("RM-FL-AP", 80), ("RM-BU-UN", 55), ("RM-MK-WH", 20), ("RM-SG-WH", 12)]),
    ("PR-PN-CL", "Cinnamon roll", "Pastries", "unit", "1100", 10,
     [("RM-FL-AP", 90), ("RM-BU-UN", 25), ("RM-SG-BR", 20), ("RM-CN-PD", 5), ("RM-YE-DR", 2)]),
    ("PR-PN-DA", "Danish pastry", "Pastries", "unit", "1300", 8,
     [("RM-FL-AP", 90), ("RM-BU-UN", 40), ("RM-EG-LG", 1), ("RM-SG-WH", 15)]),
    ("PR-PN-EC", "Éclair (chocolate)", "Pastries", "unit", "1500", 6,
     [("RM-FL-AP", 60), ("RM-BU-UN", 30), ("RM-EG-LG", 1), ("RM-CH-DK", 20), ("RM-MK-CR", 30)]),
    ("PR-CK-RD", "Red velvet slice", "Cakes", "unit", "2500", 5,
     [("RM-FL-AP", 70), ("RM-SG-WH", 60), ("RM-BU-UN", 30), ("RM-EG-LG", 1), ("RM-MK-WH", 30)]),
    ("PR-CK-CC", "Chocolate cake slice", "Cakes", "unit", "2400", 5,
     [("RM-FL-AP", 70), ("RM-SG-WH", 50), ("RM-BU-UN", 35), ("RM-CH-DK", 40), ("RM-EG-LG", 1)]),
    ("PR-CK-VA", "Vanilla cake slice", "Cakes", "unit", "2200", 5,
     [("RM-FL-AP", 70), ("RM-SG-WH", 55), ("RM-BU-UN", 30), ("RM-VA-EX", 3), ("RM-EG-LG", 1)]),
    ("PR-CK-CR", "Carrot cake slice", "Cakes", "unit", "2400", 4,
     [("RM-FL-AP", 70), ("RM-SG-BR", 50), ("RM-OL-VE", 30), ("RM-CN-PD", 3), ("RM-EG-LG", 1)]),
    ("PR-CK-CH", "Cheesecake slice", "Cakes", "unit", "2800", 4,
     [("RM-FL-AP", 30), ("RM-SG-WH", 50), ("RM-EG-LG", 1), ("RM-MK-CR", 80), ("RM-VA-EX", 2)]),
    ("PR-CK-FR", "Fresh fruit tart", "Cakes", "unit", "3000", 4,
     [("RM-FL-AP", 80), ("RM-BU-UN", 40), ("RM-SG-WH", 30), ("RM-FR-ST", 60), ("RM-EG-LG", 1)]),
    ("PR-CO-CH", "Chocolate chip cookie", "Cookies", "unit", "600", 20,
     [("RM-FL-AP", 30), ("RM-SG-BR", 15), ("RM-BU-UN", 15), ("RM-CH-MK", 20)]),
    ("PR-CO-OA", "Oatmeal cookie", "Cookies", "unit", "550", 20,
     [("RM-FL-AP", 25), ("RM-SG-BR", 12), ("RM-BU-UN", 12), ("RM-CN-PD", 1)]),
    ("PR-CO-BR", "Shortbread cookie", "Cookies", "unit", "500", 20,
     [("RM-FL-AP", 20), ("RM-SG-WH", 10), ("RM-BU-UN", 15)]),
    ("PR-CO-MA", "Macaron (assorted)", "Cookies", "unit", "1500", 10,
     [("RM-FL-AP", 8), ("RM-SG-WH", 20), ("RM-EG-LG", 1)]),
    ("PR-BV-CO", "Espresso coffee", "Beverages", "unit", "1500", 0,
     [("RM-CF-GR", 18)]),
    ("PR-BV-LA", "Café latte", "Beverages", "unit", "2000", 0,
     [("RM-CF-GR", 18), ("RM-MK-WH", 150)]),
    ("PR-BV-CA", "Cappuccino", "Beverages", "unit", "2000", 0,
     [("RM-CF-GR", 18), ("RM-MK-WH", 120)]),
    ("PR-BV-TE", "Black tea", "Beverages", "unit", "1200", 0,
     [("RM-TE-LF", 5)]),
    ("PR-BV-HC", "Hot chocolate", "Beverages", "unit", "2200", 0,
     [("RM-MK-WH", 200), ("RM-CH-MK", 25), ("RM-SG-WH", 10)]),
    ("PR-SW-HC", "Ham & cheese sandwich", "Sandwiches", "unit", "3000", 4,
     [("RM-FL-BR", 120), ("RM-BU-UN", 10)]),
    ("PR-SW-EG", "Egg sandwich", "Sandwiches", "unit", "2500", 4,
     [("RM-FL-BR", 120), ("RM-EG-LG", 2), ("RM-BU-UN", 10)]),
    ("PR-SW-VE", "Veggie wrap", "Sandwiches", "unit", "2800", 4,
     [("RM-FL-AP", 100), ("RM-OL-VE", 10)]),
    ("PR-SW-CH", "Grilled cheese", "Sandwiches", "unit", "2600", 4,
     [("RM-FL-BR", 120), ("RM-BU-UN", 20)]),
]

EXPENSE_CATEGORIES = [
    ("Rent", "Storefront and kitchen rent"),
    ("Utilities", "Electricity, water, gas, internet"),
    ("Payroll", "Staff salaries and wages"),
    ("Marketing", "Local ads, social media, flyers"),
    ("Maintenance", "Equipment repairs and upkeep"),
    ("Cleaning supplies", "Detergents, gloves, sanitizer"),
    ("Packaging", "Boxes, bags, wrappers, labels"),
    ("Transport", "Deliveries, fuel, fleet costs"),
    ("Office supplies", "Stationery, printer ink, paper"),
    ("Other", "Miscellaneous business expenses"),
]


class Command(BaseCommand):
    help = "Seed the database with realistic bakery demo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty", action="store_true",
            help="Only seed when the DB has no Products yet.",
        )
        parser.add_argument(
            "--fresh", action="store_true",
            help="Wipe demo data before reseeding (dev only).",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and Product.objects.exists():
            self.stdout.write(self.style.NOTICE("Database already has data; skipping seed."))
            return

        if options["fresh"]:
            self.stdout.write(self.style.WARNING("Wiping demo data..."))
            with transaction.atomic():
                StockMovement.objects.all().delete()
                Sale.objects.all().delete()
                ProductionRun.objects.all().delete()
                Expense.objects.all().delete()
                Invoice.objects.all().delete()
                Budget.objects.all().delete()
                StockItem.objects.all().delete()
                RecipeItem.objects.all().delete()
                Product.objects.all().delete()
                RawMaterial.objects.all().delete()
                ProductCategory.objects.all().delete()
                ExpenseCategory.objects.all().delete()
                Supplier.objects.all().delete()
                User.objects.exclude(is_superuser=True).delete()

        with transaction.atomic():
            users = self._seed_users()
            suppliers = self._seed_suppliers()
            categories = self._seed_categories()
            materials = self._seed_raw_materials(suppliers)
            products = self._seed_products(categories, materials)
            self._seed_initial_stock(materials, products, users[0])
            self._seed_expense_categories()
            self._seed_budgets()
            self._seed_history(products, users)
            self._seed_invoices(users[0])

        self.stdout.write(self.style.SUCCESS(
            "✓ Seed complete: %d products, %d raw materials, 90 days of history."
            % (len(products), len(materials))
        ))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _seed_users(self) -> list[User]:
        admin_email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@adminator.local")
        admin_password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin12345")
        admin_name = os.environ.get("DJANGO_SUPERUSER_FULL_NAME", "Site Admin")

        admin, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "full_name": admin_name,
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password(admin_password)
            admin.save()
            self.stdout.write(f"  → admin: {admin_email} / {admin_password}")

        staff = [admin]
        defaults = [
            ("manager@adminator.local", "Aline Mukamana", Role.MANAGER),
            ("accountant@adminator.local", "Eric Habimana", Role.ACCOUNTANT),
            ("cashier1@adminator.local", "Patricia Uwase", Role.CASHIER),
            ("cashier2@adminator.local", "Jean Pierre Niyonzima", Role.CASHIER),
            ("baker@adminator.local", "Sarah Ingabire", Role.STAFF),
        ]
        for email, name, role in defaults:
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={"full_name": name, "role": role, "is_active": True},
            )
            if was_created:
                user.set_password("demo12345")
                user.save()
            staff.append(user)
        return staff

    def _seed_suppliers(self) -> list[Supplier]:
        out = []
        for name, contact, phone, email in SUPPLIERS:
            obj, _ = Supplier.objects.get_or_create(
                name=name,
                defaults={"contact_name": contact, "phone": phone, "email": email},
            )
            out.append(obj)
        return out

    def _seed_categories(self) -> dict[str, ProductCategory]:
        out = {}
        for name in CATEGORIES:
            obj, _ = ProductCategory.objects.get_or_create(name=name)
            out[name] = obj
        return out

    def _seed_raw_materials(self, suppliers: list[Supplier]) -> dict[str, RawMaterial]:
        out = {}
        for sku, name, unit, cost, threshold, sup_idx in RAW_MATERIALS:
            obj, _ = RawMaterial.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "unit": unit,
                    "unit_cost": Decimal(cost),
                    "reorder_threshold": Decimal(threshold),
                    "preferred_supplier": suppliers[sup_idx],
                },
            )
            out[sku] = obj
        return out

    def _seed_products(self, categories: dict, materials: dict) -> list[Product]:
        out = []
        for sku, name, cat, unit, price, threshold, recipe in PRODUCTS:
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": categories[cat],
                    "unit": unit,
                    "selling_price": Decimal(price),
                    "reorder_threshold": threshold,
                },
            )
            # Compute production cost from recipe.
            total_cost = Decimal("0")
            RecipeItem.objects.filter(product=product).delete()
            for material_sku, qty in recipe:
                material = materials[material_sku]
                RecipeItem.objects.create(
                    product=product,
                    raw_material=material,
                    quantity=Decimal(str(qty)),
                )
                total_cost += Decimal(str(qty)) * Decimal(material.unit_cost)
            product.production_cost = total_cost.quantize(Decimal("0.01"))
            product.save(update_fields=["production_cost"])
            out.append(product)
        return out

    def _seed_initial_stock(self, materials: dict, products: list, user) -> None:
        # Generous starting stock of raw materials.
        for sku, material in materials.items():
            initial = Decimal(material.reorder_threshold) * Decimal("8")
            if initial == 0:
                initial = Decimal("5000")
            stock = inventory_services.ensure_stock_item(raw_material=material)
            if stock.quantity == 0:
                inventory_services.adjust_stock(
                    stock_item=stock,
                    quantity_delta=initial,
                    reason="purchase",
                    reference="OPENING-BALANCE",
                    note="Initial stock from seed",
                    user=user,
                )
        # Modest starting stock of finished products.
        for product in products:
            stock = inventory_services.ensure_stock_item(product=product)
            if stock.quantity == 0:
                qty = Decimal(product.reorder_threshold + RNG.randint(10, 40))
                if qty > 0:
                    inventory_services.adjust_stock(
                        stock_item=stock,
                        quantity_delta=qty,
                        reason="adjustment_in",
                        reference="OPENING-BALANCE",
                        note="Initial finished-product stock",
                        user=user,
                    )

    def _seed_expense_categories(self) -> None:
        for name, desc in EXPENSE_CATEGORIES:
            ExpenseCategory.objects.get_or_create(
                name=name, defaults={"description": desc}
            )

    def _seed_budgets(self) -> None:
        today = timezone.localdate()
        first_of_month = today.replace(day=1)
        budgets = {
            "Rent": "1500000",
            "Utilities": "350000",
            "Payroll": "4500000",
            "Marketing": "300000",
            "Maintenance": "200000",
            "Cleaning supplies": "120000",
            "Packaging": "250000",
            "Transport": "200000",
            "Office supplies": "80000",
            "Other": "150000",
        }
        for name, amount in budgets.items():
            cat = ExpenseCategory.objects.get(name=name)
            Budget.objects.update_or_create(
                category=cat,
                month=first_of_month,
                defaults={"amount": Decimal(amount)},
            )

    def _seed_history(self, products: list, users: list) -> None:
        """90 days of plausible sales, expenses, and production."""
        today = timezone.localdate()
        cashiers = [u for u in users if u.role in (Role.CASHIER, Role.MANAGER)] or users

        # Expense schedule: monthly rent + utilities + payroll, sporadic others.
        expense_categories = {c.name: c for c in ExpenseCategory.objects.all()}
        for offset in range(90, 0, -1):
            day = today - timedelta(days=offset)

            # Monthly recurring on the 1st.
            if day.day == 1:
                Expense.objects.create(
                    category=expense_categories["Rent"], title="Monthly rent",
                    amount=Decimal("1500000"), incurred_on=day,
                    payment_method="bank_transfer", recorded_by=users[0],
                )
                Expense.objects.create(
                    category=expense_categories["Payroll"], title="Staff salaries",
                    amount=Decimal("4500000"), incurred_on=day,
                    payment_method="bank_transfer", recorded_by=users[0],
                )
            # Utilities every 15th.
            if day.day == 15:
                Expense.objects.create(
                    category=expense_categories["Utilities"],
                    title="Electricity + water",
                    amount=Decimal(str(280000 + RNG.randint(-30000, 50000))),
                    incurred_on=day, payment_method="mobile_money", recorded_by=users[0],
                )
            # Sporadic small expenses.
            if RNG.random() < 0.35:
                cat = RNG.choice([
                    "Cleaning supplies", "Packaging", "Transport",
                    "Office supplies", "Maintenance", "Marketing", "Other",
                ])
                Expense.objects.create(
                    category=expense_categories[cat],
                    title=f"{cat} purchase",
                    amount=Decimal(str(RNG.randint(8000, 65000))),
                    incurred_on=day,
                    payment_method=RNG.choice(["cash", "mobile_money", "card"]),
                    recorded_by=RNG.choice(users[:3]),
                )

        # Production + sales for the last 90 days.
        for offset in range(90, -1, -1):
            day = today - timedelta(days=offset)
            weekday = day.weekday()
            # Weekend boost.
            base_multiplier = 1.5 if weekday >= 5 else 1.0
            # Friday is also busy.
            if weekday == 4:
                base_multiplier = 1.2

            # Morning production run for each frequently-sold product family.
            for product in products:
                # Beverages aren't pre-produced.
                if product.category.name == "Beverages":
                    continue
                base_qty = {
                    "Breads": 25, "Pastries": 30, "Cakes": 12,
                    "Cookies": 50, "Sandwiches": 18,
                }.get(product.category.name, 15)
                qty = int(base_qty * base_multiplier * RNG.uniform(0.7, 1.3))
                if qty <= 0:
                    continue
                # Try, skip if not enough materials (early dates).
                try:
                    production_services.execute_production(
                        product=product,
                        quantity=Decimal(qty),
                        scheduled_for=day,
                        notes=f"Morning bake {day}",
                        user=RNG.choice(users),
                    )
                except Exception:
                    pass

            # Sales across the day. Peaks at 7-9 AM and 12-2 PM and 5-7 PM.
            receipts_target = int(40 * base_multiplier * RNG.uniform(0.8, 1.2))
            for _ in range(receipts_target):
                hour = self._draw_busy_hour()
                minute = RNG.randint(0, 59)
                occurred = timezone.make_aware(
                    datetime.combine(day, time(hour=hour, minute=minute))
                )

                num_items = RNG.choices([1, 2, 3, 4, 5], weights=[3, 5, 4, 2, 1])[0]
                chosen_products = RNG.sample(products, k=min(num_items, len(products)))
                items = []
                for prod in chosen_products:
                    qty = RNG.choices([1, 2, 3], weights=[6, 3, 1])[0]
                    items.append({"product": prod, "quantity": Decimal(qty)})

                payment = RNG.choices(
                    [PaymentMethod.CASH, PaymentMethod.MOBILE_MONEY,
                     PaymentMethod.CARD, PaymentMethod.BANK_TRANSFER],
                    weights=[5, 4, 2, 1],
                )[0]
                channel = RNG.choices(
                    [SaleChannel.COUNTER, SaleChannel.ONLINE,
                     SaleChannel.DELIVERY, SaleChannel.WHOLESALE],
                    weights=[7, 2, 1, 1],
                )[0]
                try:
                    sales_services.create_sale(
                        items=items,
                        payment_method=payment,
                        channel=channel,
                        occurred_at=occurred,
                        user=RNG.choice(cashiers),
                        allow_negative_stock=True,  # demo only
                    )
                except Exception:
                    pass

    def _draw_busy_hour(self) -> int:
        # Weighted distribution across operating hours (6-21).
        hours = list(range(6, 22))
        weights = [1, 2, 5, 6, 5, 3, 3, 6, 7, 4, 2, 2, 4, 6, 4, 2]
        return RNG.choices(hours, weights=weights)[0]

    def _seed_invoices(self, user) -> None:
        wholesale_customers = [
            "Café Innovation", "Hotel Mille Collines", "Kigali Heights Office",
            "Sunrise Catering", "Lakeview Restaurant", "Greenpark Hotel",
        ]
        today = timezone.localdate()
        for i in range(15):
            issue = today - timedelta(days=RNG.randint(0, 60))
            due = issue + timedelta(days=RNG.choice([7, 14, 30]))
            amount = Decimal(str(RNG.randint(40000, 380000)))
            status_pool = [
                InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.PAID, InvoiceStatus.PAID, InvoiceStatus.OVERDUE,
            ]
            status = RNG.choice(status_pool)
            paid = Decimal("0")
            paid_at = None
            if status == InvoiceStatus.PAID:
                paid = amount
                paid_at = timezone.make_aware(datetime.combine(
                    due - timedelta(days=RNG.randint(0, 5)), time(12, 0)
                ))
            elif status == InvoiceStatus.PARTIALLY_PAID:
                paid = amount * Decimal(str(RNG.uniform(0.2, 0.7))).quantize(Decimal("0.01"))
            customer = RNG.choice(wholesale_customers)
            Invoice.objects.create(
                invoice_number=f"INV-{today.year}-{1000 + i}",
                customer_name=customer,
                customer_email=f"orders@{customer.lower().replace(' ', '')}.rw",
                issue_date=issue,
                due_date=due,
                amount=amount,
                amount_paid=paid,
                status=status,
                paid_at=paid_at,
                description="Wholesale order — assorted bakery items.",
                issued_by=user,
            )
