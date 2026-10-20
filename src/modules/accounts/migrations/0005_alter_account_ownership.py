from django.db import migrations, models


class Migration(migrations.Migration):
    """Ownership is now chosen from each company's own options, so the fixed
    list of choices is dropped (same change as Leads' dropdown fields)."""

    dependencies = [
        ("accounts", "0004_backfill_account_company"),
    ]

    operations = [
        migrations.AlterField(
            model_name="djangoaccountmodel",
            name="ownership",
            field=models.CharField(default="None", max_length=50),
        ),
    ]
