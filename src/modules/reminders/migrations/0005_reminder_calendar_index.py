from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0004_backfill_reminder_company"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangoremindermodel",
            index=models.Index(
                fields=["company", "remind_at"],
                name="reminders_co_remind_idx",
            ),
        ),
    ]
