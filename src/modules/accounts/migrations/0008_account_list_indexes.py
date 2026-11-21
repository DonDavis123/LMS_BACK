from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_account_summary"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangoaccountmodel",
            index=models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="accounts_co_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangoaccountmodel",
            index=models.Index(
                fields=["company", "is_deleted", "account_owner"],
                name="accounts_co_owner_idx",
            ),
        ),
    ]
