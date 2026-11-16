from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0006_meeting_google_meet_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="participant_reminder_for",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
