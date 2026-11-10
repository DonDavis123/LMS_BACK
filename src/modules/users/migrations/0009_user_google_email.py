from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_backfill_user_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="google_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
