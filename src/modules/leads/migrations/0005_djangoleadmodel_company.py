import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("leads", "0004_alter_djangoleadmodel_company_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangoleadmodel",
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
