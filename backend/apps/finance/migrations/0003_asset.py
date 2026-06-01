import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
        ('finance', '0002_transaction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=160)),
                ('category', models.CharField(
                    choices=[
                        ('equipment', 'Equipment'),
                        ('furniture', 'Furniture'),
                        ('vehicle', 'Vehicle'),
                        ('electronics', 'Electronics'),
                        ('fit_out', 'Shop fit-out'),
                        ('other', 'Other'),
                    ],
                    default='equipment',
                    max_length=20,
                )),
                ('purchase_date', models.DateField(default=django.utils.timezone.localdate)),
                ('purchase_cost', models.DecimalField(
                    decimal_places=2, max_digits=14,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                )),
                ('useful_life_months', models.PositiveIntegerField(
                    blank=True, null=True,
                    help_text='Months over which to straight-line depreciate. Leave blank for no depreciation.',
                )),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('disposed', 'Disposed')],
                    default='active',
                    max_length=10,
                )),
                ('reference', models.CharField(
                    blank=True, max_length=80,
                    help_text='Invoice / receipt number.',
                )),
                ('notes', models.TextField(blank=True)),
                ('supplier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assets', to='catalog.supplier',
                )),
                ('linked_expense', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='asset', to='finance.expense',
                    help_text='Optional Expense row created at purchase time so cash-out shows in P&L.',
                )),
                ('recorded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assets', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-purchase_date', '-created_at'],
                'indexes': [
                    models.Index(fields=['-purchase_date'], name='finance_ass_purchas_idx'),
                    models.Index(fields=['category', '-purchase_date'], name='finance_ass_categor_idx'),
                    models.Index(fields=['status'], name='finance_ass_status_idx'),
                ],
            },
        ),
    ]
