from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangoremindermodel",
            name="is_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
