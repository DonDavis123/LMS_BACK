from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0011_lead_summary"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=models.Index(
                fields=["company", "is_deleted", "is_converted", "owner"],
                name="leads_co_owner_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=models.Index(
                fields=["company", "is_deleted", "is_converted", "lead_status"],
                name="leads_co_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=models.Index(
                fields=["company", "is_deleted", "is_converted", "lead_source"],
                name="leads_co_source_idx",
            ),
        ),
    ]
