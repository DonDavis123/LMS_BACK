from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lead_capture", "0002_backfill_lead_forms"),
    ]

    operations = [
        # Safe for existing rows: the count defaults to 0 and the date to NULL.
        migrations.AddField(
            model_name="djangoleadformmodel",
            name="daily_submission_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="djangoleadformmodel",
            name="daily_submission_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
