import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):

    dependencies = [
        ("processed_materials", "0002_processedmaterial_overhead_pct"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="processedmaterialrecipeitem",
            name="unique_pm_raw_material",
        ),
        migrations.AlterField(
            model_name="processedmaterialrecipeitem",
            name="raw_material",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="used_in_processed",
                to="catalog.rawmaterial",
            ),
        ),
        migrations.AddField(
            model_name="processedmaterialrecipeitem",
            name="sub_processed_material",
            field=models.ForeignKey(
                blank=True,
                help_text="Another processed material used as an ingredient in this recipe.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="used_in_processed_materials",
                to="processed_materials.processedmaterial",
            ),
        ),
        migrations.AlterModelOptions(
            name="processedmaterialrecipeitem",
            options={
                "ordering": [
                    "processed_material",
                    "raw_material",
                    "sub_processed_material",
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="processedmaterialrecipeitem",
            constraint=models.UniqueConstraint(
                condition=Q(raw_material__isnull=False),
                fields=("processed_material", "raw_material"),
                name="unique_pm_raw_material",
            ),
        ),
        migrations.AddConstraint(
            model_name="processedmaterialrecipeitem",
            constraint=models.UniqueConstraint(
                condition=Q(sub_processed_material__isnull=False),
                fields=("processed_material", "sub_processed_material"),
                name="unique_pm_sub_processed_material",
            ),
        ),
        migrations.AddConstraint(
            model_name="processedmaterialrecipeitem",
            constraint=models.CheckConstraint(
                check=(
                    Q(raw_material__isnull=False, sub_processed_material__isnull=True)
                    | Q(raw_material__isnull=True, sub_processed_material__isnull=False)
                ),
                name="pm_recipe_item_exactly_one_ingredient",
            ),
        ),
        migrations.AddConstraint(
            model_name="processedmaterialrecipeitem",
            constraint=models.CheckConstraint(
                check=~Q(sub_processed_material=F("processed_material")),
                name="pm_recipe_item_no_self_reference",
            ),
        ),
    ]
