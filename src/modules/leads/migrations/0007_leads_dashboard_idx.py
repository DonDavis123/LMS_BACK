from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0006_backfill_lead_company"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=models.Index(
                fields=["company", "is_deleted", "is_converted", "created_at"],
                name="leads_dashboard_idx",
            ),
        ),
    ]
