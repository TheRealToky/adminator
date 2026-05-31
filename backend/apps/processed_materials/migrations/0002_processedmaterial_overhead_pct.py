import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("processed_materials", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="processedmaterial",
            name="overhead_pct",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="Variable overhead estimate as a percentage of ingredient cost.",
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="processedmaterial",
            name="unit_cost",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                help_text="Derived: (batch cost + overhead) / yield_per_batch.",
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
    ]
