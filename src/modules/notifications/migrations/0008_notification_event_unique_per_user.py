from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """Allow one notification per recipient for the same task/reminder event.

    A task's owner and its assigned user are both notified about the same
    due date or reminder, so the uniqueness of those events is per user.
    """

    dependencies = [
        ("notifications", "0007_backfill_notification_company"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="djangonotificationmodel",
            name="notification_reminder_event_unique",
        ),
        migrations.RemoveConstraint(
            model_name="djangonotificationmodel",
            name="notification_task_event_unique",
        ),
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "scheduled_for", "reminder", "user"),
                condition=Q(reminder__isnull=False),
                name="notification_reminder_event_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="djangonotificationmodel",
            constraint=models.UniqueConstraint(
                fields=("notification_type", "scheduled_for", "task", "user"),
                condition=Q(task__isnull=False),
                name="notification_task_event_unique",
            ),
        ),
    ]
