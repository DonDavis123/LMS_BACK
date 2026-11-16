from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0009_backfill_send_email_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="reminder_offsets",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="reminders_sent_for",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="reminder_subject",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="reminder_message",
            field=models.TextField(blank=True, null=True),
        ),
    ]
