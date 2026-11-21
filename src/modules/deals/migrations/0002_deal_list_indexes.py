from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("deals", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangodealmodel",
            index=models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="deals_co_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangodealmodel",
            index=models.Index(
                fields=["company", "is_deleted", "owner"],
                name="deals_co_owner_idx",
            ),
        ),
    ]
