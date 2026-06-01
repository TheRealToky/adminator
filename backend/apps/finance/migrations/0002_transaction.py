import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionCategory',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=80)),
                ('direction', models.CharField(choices=[('income', 'Income'), ('expense', 'Expense')], default='expense', max_length=8)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'transaction categories',
                'ordering': ['direction', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='transactioncategory',
            constraint=models.UniqueConstraint(
                fields=('name', 'direction'),
                name='unique_tx_category_name_direction',
            ),
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('direction', models.CharField(choices=[('income', 'Income'), ('expense', 'Expense')], default='expense', max_length=8)),
                ('title', models.CharField(max_length=160)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('occurred_on', models.DateField(default=django.utils.timezone.localdate)),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('mobile_money', 'Mobile Money'), ('card', 'Card'), ('bank_transfer', 'Bank Transfer')], default='cash', max_length=16)),
                ('counterparty', models.CharField(blank=True, help_text='Free-form: customer for income, supplier for expense.', max_length=160)),
                ('reference', models.CharField(blank=True, max_length=80)),
                ('notes', models.TextField(blank=True)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='finance.transactioncategory')),
            ],
            options={
                'ordering': ['-occurred_on', '-created_at'],
                'indexes': [
                    models.Index(fields=['-occurred_on'], name='finance_tx_occurre_idx'),
                    models.Index(fields=['direction', '-occurred_on'], name='finance_tx_directi_idx'),
                    models.Index(fields=['category', '-occurred_on'], name='finance_tx_categor_idx'),
                ],
            },
        ),
    ]
