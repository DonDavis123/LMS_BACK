from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meetings", "0010_meeting_reminder_options"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangomeetingmodel",
            index=models.Index(
                fields=["company", "is_deleted", "start_at"],
                name="meetings_co_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangomeetingmodel",
            index=models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="meetings_co_created_idx",
            ),
        ),
    ]
