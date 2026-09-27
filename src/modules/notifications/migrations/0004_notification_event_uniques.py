from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "scheduled_for", "reminder"),
                condition=Q(reminder__isnull=False),
                name="notification_reminder_event_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "scheduled_for", "task"),
                condition=Q(task__isnull=False),
                name="notification_task_event_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "scheduled_for", "meeting"),
                condition=Q(meeting__isnull=False),
                name="notification_meeting_event_unique",
            ),
        ),
    ]
