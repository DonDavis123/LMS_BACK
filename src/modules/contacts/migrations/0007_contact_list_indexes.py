from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0006_contact_summary"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="contacts_co_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=models.Index(
                fields=["company", "is_deleted", "contact_owner"],
                name="contacts_co_owner_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=models.Index(
                fields=["company", "is_deleted", "account"],
                name="contacts_co_account_idx",
            ),
        ),
    ]
