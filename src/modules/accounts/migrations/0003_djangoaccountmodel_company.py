import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("accounts", "0002_drop_unique_active_account_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangoaccountmodel",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="companies.djangocompanymodel",
            ),
        ),
    ]
