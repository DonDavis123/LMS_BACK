from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """Notifications can report on a finished lead import.

    Adds the ``LEAD_IMPORT_FINISHED`` type, the id of the import the
    notification opens, and a database guarantee of one such notification per
    import and user.
    """

    dependencies = [
        ("notifications", "0008_notification_event_unique_per_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="djangonotificationmodel",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("REMINDER", "REMINDER"),
                    ("TASK_DUE_ONE_DAY", "TASK_DUE_ONE_DAY"),
                    ("TASK_DUE_TODAY", "TASK_DUE_TODAY"),
                    ("MEETING_ONE_DAY", "MEETING_ONE_DAY"),
                    ("MEETING_TODAY", "MEETING_TODAY"),
                    ("LEAD_IMPORT_FINISHED", "LEAD_IMPORT_FINISHED"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="djangonotificationmodel",
            name="lead_import_job_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "lead_import_job_id", "user"),
                condition=Q(lead_import_job_id__isnull=False),
                name="notification_lead_import_event_unique",
            ),
        ),
    ]
