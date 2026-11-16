from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0007_meeting_participant_reminder_for"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="send_email_notifications",
            field=models.BooleanField(default=False),
        ),
    ]
