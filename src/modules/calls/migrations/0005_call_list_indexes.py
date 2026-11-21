from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0004_call_recording_transcripts"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="djangocallmodel",
            index=models.Index(
                fields=["company", "is_deleted", "call_start_time"],
                name="calls_co_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangocallmodel",
            index=models.Index(
                fields=["company", "is_deleted", "status"],
                name="calls_co_status_idx",
            ),
        ),
    ]
