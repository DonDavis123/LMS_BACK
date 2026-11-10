from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0001_initial"),
    ]

    operations = [
        # Every existing call is a logged (completed) call.
        migrations.AddField(
            model_name="djangocallmodel",
            name="status",
            field=models.CharField(
                choices=[
                    ("Planned", "Planned"),
                    ("Completed", "Completed"),
                    ("Missed", "Missed"),
                ],
                default="Completed",
                max_length=100,
            ),
        ),
        # Planned / missed calls have no outcome yet.
        migrations.AlterField(
            model_name="djangocallmodel",
            name="outcome",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                choices=[
                    ("Connected", "Connected"),
                    ("Not Attended", "Not Attended"),
                    ("Busy", "Busy"),
                    ("Voicemail", "Voicemail"),
                    ("Wrong Number", "Wrong Number"),
                    ("Callback Requested", "Callback Requested"),
                ],
            ),
        ),
        migrations.AddIndex(
            model_name="djangocallmodel",
            index=models.Index(
                fields=["company", "owner", "call_start_time"],
                name="calls_co_owner_start_idx",
            ),
        ),
    ]
