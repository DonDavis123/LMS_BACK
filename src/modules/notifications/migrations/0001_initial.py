import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("meetings", "0002_remove_djangomeetingparticipantmodel_meeting_participant_type_match_and_more"),
        ("reminders", "0001_initial"),
        ("tasks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoNotificationModel",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("REMINDER", "REMINDER"),
                            ("TASK_DUE_ONE_DAY", "TASK_DUE_ONE_DAY"),
                            ("TASK_DUE_TODAY", "TASK_DUE_TODAY"),
                            ("MEETING_ONE_DAY", "MEETING_ONE_DAY"),
                            ("MEETING_TODAY", "MEETING_TODAY"),
                        ],
                        max_length=30,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("scheduled_for", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="meetings.djangomeetingmodel",
                    ),
                ),
                (
                    "reminder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="reminders.djangoremindermodel",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="tasks.djangotaskmodel",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "notifications",
                "indexes": [
                    models.Index(fields=["user", "scheduled_for"], name="notif_user_sched_idx"),
                    models.Index(fields=["user", "is_read"], name="notif_user_read_idx"),
                    models.Index(fields=["expires_at"], name="notif_expires_idx"),
                    models.Index(fields=["scheduled_for"], name="notif_sched_idx"),
                    models.Index(fields=["task"], name="notif_task_idx"),
                    models.Index(fields=["meeting"], name="notif_meeting_idx"),
                    models.Index(fields=["reminder"], name="notif_reminder_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(meeting__isnull=True) | models.Q(task__isnull=True),
                        name="notification_single_target",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(is_read=False, read_at__isnull=True)
                            | models.Q(is_read=True, read_at__isnull=False)
                        ),
                        name="notification_read_state_match",
                    ),
                ],
            },
        ),
    ]
