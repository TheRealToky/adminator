"""
Seed processed-material demo data.

Adds 5 realistic processed materials (dough, batter, ganache, etc.), links them
to existing products as bill-of-materials inputs, runs a handful of historical
batches so on-hand stock is non-zero, and creates a few new "composed" products
that use them.

Usage:
    python manage.py seed_processed_materials
    python manage.py seed_processed_materials --if-empty
    python manage.py seed_processed_materials --fresh   # wipe & reseed (dev)
"""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product, ProductCategory, RawMaterial

from ...models import (
    ProcessedMaterial,
    ProcessedMaterialBatch,
    ProcessedMaterialRecipeItem,
    ProcessedMaterialStock,
    ProcessedMaterialStockMovement,
    ProductProcessedMaterialUsage,
)
from ... import services as pm_services

User = get_user_model()
RNG = random.Random(7)


# ── Reference data ────────────────────────────────────────────────────────
# (sku, name, unit, yield_per_batch, shelf_life_hours, reorder_threshold,
#  recipe: [(raw_material_sku, qty_per_batch), ...], notes)
PROCESSED_MATERIALS = [
    (
        "PM-DG-PZ", "Pizza dough", "g", "8000", 24, "2000",
        [
            ("RM-FL-BR", 5000),  # bread flour
            ("RM-OL-VE", 200),   # vegetable oil
            ("RM-SL-FI", 100),   # fine salt
            ("RM-YE-DR", 60),    # dry yeast
        ],
        "Stretchable pizza dough — rest 24h cold for best flavor.",
    ),
    (
        "PM-BT-CR", "Crepe batter", "ml", "6000", 48, "1500",
        [
            ("RM-FL-AP", 1200),  # all-purpose flour
            ("RM-EG-LG", 8),     # eggs
            ("RM-MK-WH", 3000),  # whole milk
            ("RM-SG-WH", 100),   # sugar
            ("RM-SL-FI", 10),    # salt
            ("RM-BU-UN", 80),    # butter (melted)
        ],
        "Lightly sweet crepe batter — strain through fine sieve before use.",
    ),
    (
        "PM-GN-DK", "Dark chocolate ganache", "g", "2000", 72, "500",
        [
            ("RM-CH-DK", 1000),  # dark chocolate
            ("RM-MK-CR", 1000),  # heavy cream
        ],
        "1:1 ganache — pipeable when set, pourable while warm.",
    ),
    (
        "PM-CR-PT", "Pastry cream (crème pâtissière)", "g", "2400", 36, "600",
        [
            ("RM-MK-WH", 1500),  # whole milk
            ("RM-EG-LG", 8),     # eggs (yolks, simplified)
            ("RM-SG-WH", 300),   # sugar
            ("RM-FL-AP", 100),   # all-purpose flour (or cornstarch substitute)
            ("RM-VA-EX", 15),    # vanilla extract
        ],
        "Classic vanilla pastry cream for éclairs and tarts.",
    ),
    (
        "PM-DG-CR", "Croissant dough (laminated)", "g", "6000", 24, "1500",
        [
            ("RM-FL-AP", 3000),  # all-purpose flour
            ("RM-BU-UN", 1800),  # butter (for lamination)
            ("RM-MK-WH", 800),   # whole milk
            ("RM-SG-WH", 300),   # sugar
            ("RM-YE-DR", 30),    # dry yeast
            ("RM-SL-FI", 40),    # salt
        ],
        "Laminated dough — three folds, cold rest between each.",
    ),
]


# (product_sku, processed_material_sku, qty_per_product_unit)
# Existing products from the original seed are reused; we also add a few new ones below.
PRODUCT_USAGES = [
    # Croissants — laminated dough replaces raw butter/flour as the main input
    ("PR-CR-PL", "PM-DG-CR", "60"),
    ("PR-CR-CH", "PM-DG-CR", "60"),
    ("PR-CR-AL", "PM-DG-CR", "60"),
    # Éclair uses pastry cream
    ("PR-PN-EC", "PM-CR-PT", "40"),
    # Chocolate cake slice gets a ganache topping
    ("PR-CK-CC", "PM-GN-DK", "30"),
    # Cinnamon roll uses (a sweet) version of croissant dough
    ("PR-PN-CL", "PM-DG-CR", "80"),
]


# New products that are SHOWCASES for processed materials (added on top, not editing existing seed).
# (sku, name, category, unit, selling_price, reorder_threshold, raw_recipe, processed_usages)
SHOWCASE_PRODUCTS = [
    (
        "PR-PZ-MA", "Pizza Margherita", "Sandwiches", "unit", "5500", 6,
        [],  # everything comes from processed material
        [("PM-DG-PZ", "250")],
    ),
    (
        "PR-PZ-PE", "Pizza Pepperoni", "Sandwiches", "unit", "6500", 6,
        [],
        [("PM-DG-PZ", "250")],
    ),
    (
        "PR-CP-NU", "Crêpe Nutella", "Pastries", "unit", "2200", 8,
        [],
        [("PM-BT-CR", "120"), ("PM-GN-DK", "20")],
    ),
    (
        "PR-CP-SF", "Crêpe sucre-citron", "Pastries", "unit", "1800", 8,
        [],
        [("PM-BT-CR", "120")],
    ),
    (
        "PR-TR-CC", "Chocolate truffle (4-pack)", "Cookies", "pack", "3500", 6,
        [],
        [("PM-GN-DK", "60")],
    ),
]


class Command(BaseCommand):
    help = "Seed processed-material demo data (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty", action="store_true",
            help="Only seed when no ProcessedMaterial records exist yet.",
        )
        parser.add_argument(
            "--fresh", action="store_true",
            help="Wipe existing processed-material data first (dev only).",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and ProcessedMaterial.objects.exists():
            self.stdout.write(self.style.NOTICE(
                "Processed materials already seeded; skipping."
            ))
            return

        if options["fresh"]:
            self.stdout.write(self.style.WARNING("Wiping processed-material data..."))
            with transaction.atomic():
                ProcessedMaterialStockMovement.objects.all().delete()
                ProcessedMaterialBatch.objects.all().delete()
                ProcessedMaterialStock.objects.all().delete()
                ProductProcessedMaterialUsage.objects.all().delete()
                ProcessedMaterialRecipeItem.objects.all().delete()
                ProcessedMaterial.objects.all().delete()

        admin = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(role="admin").first()
            or User.objects.first()
        )
        if admin is None:
            self.stdout.write(self.style.ERROR(
                "No users found — run `python manage.py seed` first."
            ))
            return

        # Sanity: required raw materials must exist (from the base seed).
        required_skus = {sku for _, _, _, _, _, _, recipe, _ in PROCESSED_MATERIALS for sku, _ in recipe}
        missing = required_skus - set(
            RawMaterial.objects.filter(sku__in=required_skus).values_list("sku", flat=True)
        )
        if missing:
            self.stdout.write(self.style.ERROR(
                f"Missing raw materials in catalog: {sorted(missing)}. "
                "Run `python manage.py seed` first."
            ))
            return

        with transaction.atomic():
            materials = self._seed_processed_materials()
            self._seed_recipes(materials)
            self._seed_showcase_products(materials)
            self._link_existing_products(materials)
            self._seed_batch_history(materials, admin)

        self.stdout.write(self.style.SUCCESS(
            f"✓ Processed-material seed complete: {len(materials)} materials, "
            f"{len(SHOWCASE_PRODUCTS)} new showcase products, "
            f"{ProcessedMaterialBatch.objects.count()} batches in history."
        ))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _seed_processed_materials(self) -> dict[str, ProcessedMaterial]:
        out: dict[str, ProcessedMaterial] = {}
        for sku, name, unit, yield_, shelf, reorder, _recipe, notes in PROCESSED_MATERIALS:
            obj, _ = ProcessedMaterial.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "unit": unit,
                    "yield_per_batch": Decimal(yield_),
                    "shelf_life_hours": shelf,
                    "reorder_threshold": Decimal(reorder),
                    "notes": notes,
                    "is_active": True,
                },
            )
            out[sku] = obj
        return out

    def _seed_recipes(self, materials: dict[str, ProcessedMaterial]) -> None:
        for sku, _, _, _, _, _, recipe, _ in PROCESSED_MATERIALS:
            material = materials[sku]
            # Wipe existing recipe lines first, so re-running the seed is idempotent.
            ProcessedMaterialRecipeItem.objects.filter(processed_material=material).delete()
            for rm_sku, qty in recipe:
                raw = RawMaterial.objects.get(sku=rm_sku)
                ProcessedMaterialRecipeItem.objects.create(
                    processed_material=material,
                    raw_material=raw,
                    quantity=Decimal(str(qty)),
                )
            # Pre-compute unit_cost from the recipe so prices look right on day 1.
            batch_cost = pm_services.compute_batch_cost(material)
            yield_ = Decimal(material.yield_per_batch)
            if yield_ > 0:
                ProcessedMaterial.objects.filter(pk=material.pk).update(
                    unit_cost=(batch_cost / yield_).quantize(Decimal("0.0001"))
                )

    def _seed_showcase_products(self, materials: dict[str, ProcessedMaterial]) -> None:
        """Add a handful of new products that demonstrate processed-material usage."""
        for sku, name, cat_name, unit, price, threshold, _raw_recipe, usages in SHOWCASE_PRODUCTS:
            category, _ = ProductCategory.objects.get_or_create(name=cat_name)
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "selling_price": Decimal(price),
                    "reorder_threshold": threshold,
                    "is_active": True,
                },
            )
            # Wipe existing processed usages on this product so the seed is idempotent.
            ProductProcessedMaterialUsage.objects.filter(product=product).delete()
            est_cost = Decimal("0")
            for pm_sku, qty in usages:
                material = materials[pm_sku]
                ProductProcessedMaterialUsage.objects.create(
                    product=product,
                    processed_material=material,
                    quantity=Decimal(str(qty)),
                )
                est_cost += Decimal(str(qty)) * Decimal(material.unit_cost)
            Product.objects.filter(pk=product.pk).update(
                production_cost=est_cost.quantize(Decimal("0.01"))
            )

    def _link_existing_products(self, materials: dict[str, ProcessedMaterial]) -> None:
        """Attach processed-material usages to products that already exist."""
        for product_sku, pm_sku, qty in PRODUCT_USAGES:
            try:
                product = Product.objects.get(sku=product_sku)
            except Product.DoesNotExist:
                continue
            material = materials[pm_sku]
            ProductProcessedMaterialUsage.objects.update_or_create(
                product=product,
                processed_material=material,
                defaults={"quantity": Decimal(str(qty))},
            )

    def _seed_batch_history(self, materials: dict[str, ProcessedMaterial], user) -> None:
        """Produce a handful of historical batches so on-hand stock isn't empty."""
        today = timezone.localdate()
        for material in materials.values():
            # Run 4-6 batches across the last 10 days.
            for _ in range(RNG.randint(4, 6)):
                day = today - timedelta(days=RNG.randint(0, 10))
                try:
                    pm_services.produce_batch(
                        processed_material=material,
                        batches=Decimal(str(RNG.choice([1, 1, 2, 2, 3]))),
                        scheduled_for=day,
                        notes="Seed batch",
                        user=user,
                    )
                except Exception:
                    # Raw material may be depleted in seed data; ignore gracefully.
                    pass
