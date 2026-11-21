from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_user_google_email"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(
                fields=["company", "deleted_at", "created_at"],
                name="users_co_created_idx",
            ),
        ),
    ]
