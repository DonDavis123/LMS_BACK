from django.db import migrations, models


class Migration(migrations.Migration):
    """Notifications can report that a lead import was undone.

    Adds the ``LEAD_IMPORT_UNDONE`` type. It is a separate type because the
    database allows one ``LEAD_IMPORT_FINISHED`` notification per import and
    user, so an "undone" notice could not share it.
    """

    dependencies = [
        ("notifications", "0009_notification_lead_import"),
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
                    ("LEAD_IMPORT_UNDONE", "LEAD_IMPORT_UNDONE"),
                ],
                max_length=30,
            ),
        ),
    ]
