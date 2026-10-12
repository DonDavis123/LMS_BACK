import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("reminders", "0002_djangoremindermodel_is_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangoremindermodel",
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
