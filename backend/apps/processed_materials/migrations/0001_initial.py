import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

UNIT_CHOICES = [
    ("g", "Gram (g)"),
    ("kg", "Kilogram (kg)"),
    ("ml", "Milliliter (ml)"),
    ("l", "Liter (l)"),
    ("unit", "Unit"),
    ("dozen", "Dozen"),
    ("pack", "Pack"),
]

REASON_CHOICES = [
    ("batch_in", "Batch produced"),
    ("production_out", "Used in product"),
    ("adjustment_in", "Manual adjustment (in)"),
    ("adjustment_out", "Manual adjustment (out)"),
    ("waste", "Waste / expired"),
]


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessedMaterial",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sku", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("unit", models.CharField(choices=UNIT_CHOICES, max_length=10)),
                (
                    "yield_per_batch",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("1"),
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "unit_cost",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("shelf_life_hours", models.PositiveIntegerField(default=24)),
                (
                    "reorder_threshold",
                    models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=12),
                ),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ProcessedMaterialRecipeItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))],
                    ),
                ),
                (
                    "processed_material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipe_items",
                        to="processed_materials.processedmaterial",
                    ),
                ),
                (
                    "raw_material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="used_in_processed",
                        to="catalog.rawmaterial",
                    ),
                ),
            ],
            options={
                "ordering": ["processed_material", "raw_material"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("processed_material", "raw_material"),
                        name="unique_pm_raw_material",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProductProcessedMaterialUsage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))],
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="processed_usages",
                        to="catalog.product",
                    ),
                ),
                (
                    "processed_material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="used_in_products",
                        to="processed_materials.processedmaterial",
                    ),
                ),
            ],
            options={
                "ordering": ["product", "processed_material"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("product", "processed_material"),
                        name="unique_product_pm",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProcessedMaterialStock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=14)),
                (
                    "processed_material",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock",
                        to="processed_materials.processedmaterial",
                    ),
                ),
            ],
            options={"ordering": ["processed_material__name"]},
        ),
        migrations.CreateModel(
            name="ProcessedMaterialStockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.CharField(choices=REASON_CHOICES, max_length=20)),
                ("quantity_delta", models.DecimalField(decimal_places=4, max_digits=14)),
                ("balance_after", models.DecimalField(decimal_places=4, max_digits=14)),
                ("reference", models.CharField(blank=True, max_length=160)),
                ("note", models.TextField(blank=True)),
                (
                    "stock",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="movements",
                        to="processed_materials.processedmaterialstock",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="processed_material_movements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["stock", "-created_at"], name="pm_mov_stock_created_idx"),
                    models.Index(fields=["reason", "-created_at"], name="pm_mov_reason_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProcessedMaterialBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "batches",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("1"),
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("quantity_produced", models.DecimalField(decimal_places=4, max_digits=14)),
                ("cost", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("scheduled_for", models.DateField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "processed_material",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="batches",
                        to="processed_materials.processedmaterial",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="processed_material_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-scheduled_for", "-created_at"],
                "indexes": [
                    models.Index(fields=["-scheduled_for"], name="pm_batch_sched_idx"),
                    models.Index(
                        fields=["processed_material", "-scheduled_for"],
                        name="pm_batch_material_sched_idx",
                    ),
                ],
            },
        ),
    ]
