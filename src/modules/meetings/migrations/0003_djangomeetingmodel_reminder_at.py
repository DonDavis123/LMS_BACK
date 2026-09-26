from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0002_remove_djangomeetingparticipantmodel_meeting_participant_type_match_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="djangomeetingmodel",
            name="reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
