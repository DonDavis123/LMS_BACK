from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from src.modules.notifications.application.use_cases.process_notifications import ProcessNotificationsUseCase
from src.modules.notifications.domain.entities.notification import Notification
from src.modules.notifications.domain.enums.notification_type import NotificationType


class _User:
    def __init__(self, user_id, is_active=True):
        self.id = user_id
        self.is_active = is_active


class _UserRepository:
    def __init__(self, users):
        self.users = {user.id: user for user in users}

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class _Task:
    def __init__(self, task_id, owner_id, due_date, subject="Call customer"):
        self.id = task_id
        self.owner_id = owner_id
        self.due_date = due_date
        self.subject = subject
        self.is_deleted = False


class _TaskRepository:
    def __init__(self, tasks):
        self.tasks = tasks

    def get_by_due_date_range(self, start_date, end_date):
        return [t for t in self.tasks if start_date <= t.due_date <= end_date]

    def get_by_id(self, task_id):
        return next((t for t in self.tasks if t.id == task_id), None)


class _Meeting:
    def __init__(self, meeting_id, host_id, start_at, title="Client Meeting"):
        self.id = meeting_id
        self.host_id = host_id
        self.start_at = start_at
        self.title = title
        self.is_deleted = False


class _MeetingRepository:
    def __init__(self, meetings):
        self.meetings = meetings

    def get_by_start_at_range(self, start_at, end_at):
        return [m for m in self.meetings if start_at <= m.start_at < end_at]

    def get_by_id(self, meeting_id):
        return next((m for m in self.meetings if m.id == meeting_id), None)


class _Reminder:
    def __init__(self, reminder_id, user_id, remind_at, subject="Pay bill", task_id=None, meeting_id=None):
        self.id = reminder_id
        self.user_id = user_id
        self.remind_at = remind_at
        self.subject = subject
        self.task_id = task_id
        self.meeting_id = meeting_id


class _ReminderRepository:
    def __init__(self, reminders):
        self.reminders = reminders

    def get_due(self, as_of):
        return [r for r in self.reminders if r.remind_at <= as_of]

    def get_by_id(self, reminder_id):
        return next((r for r in self.reminders if r.id == reminder_id), None)


class _NotificationRepository:
    def __init__(self):
        self.items = {}

    def save(self, notification):
        self.items[notification.id] = notification
        return notification

    def get_existing_for_source(self, *, notification_type, scheduled_for, task_id=None, meeting_id=None, reminder_id=None):
        for notification in self.items.values():
            if (
                notification.notification_type == notification_type
                and notification.scheduled_for == scheduled_for
                and notification.task_id == task_id
                and notification.meeting_id == meeting_id
                and notification.reminder_id == reminder_id
            ):
                return notification
        return None

    def delete_expired(self, as_of):
        ids = [i for i, n in self.items.items() if n.expires_at <= as_of]
        for i in ids:
            del self.items[i]
        return len(ids)


class _TransactionManager:
    def execute(self, operation):
        return operation()


class ProcessNotificationsUseCaseTests(SimpleTestCase):
    def setUp(self):
        self.user = _User(uuid4())
        self.user_repository = _UserRepository([self.user])
        self.notification_repository = _NotificationRepository()
        self.reminder_repository = _ReminderRepository([])
        self.task_repository = _TaskRepository([])
        self.meeting_repository = _MeetingRepository([])
        self.use_case = ProcessNotificationsUseCase(
            self.notification_repository,
            self.reminder_repository,
            self.task_repository,
            self.meeting_repository,
            self.user_repository,
            _TransactionManager(),
        )

    def test_task_due_today_creates_notification(self):
        now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
        self.task_repository.tasks.append(_Task(uuid4(), self.user.id, date(2026, 9, 27)))

        result = self.use_case.execute(now)

        self.assertEqual(result.task_notifications_created, 1)
        self.assertEqual(len(self.notification_repository.items), 1)
        notification = next(iter(self.notification_repository.items.values()))
        self.assertEqual(notification.notification_type, NotificationType.TASK_DUE_TODAY)

    def test_task_due_tomorrow_creates_notification(self):
        now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
        self.task_repository.tasks.append(_Task(uuid4(), self.user.id, date(2026, 9, 28)))

        result = self.use_case.execute(now)

        self.assertEqual(result.task_notifications_created, 1)
        self.assertEqual(next(iter(self.notification_repository.items.values())).notification_type, NotificationType.TASK_DUE_ONE_DAY)

    def test_standalone_reminder_creates_notification(self):
        now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
        self.reminder_repository.reminders.append(_Reminder(uuid4(), self.user.id, now - timedelta(minutes=1)))

        result = self.use_case.execute(now)

        self.assertEqual(result.reminders_processed, 1)
        self.assertEqual(len(self.notification_repository.items), 1)
        self.assertEqual(next(iter(self.notification_repository.items.values())).notification_type, NotificationType.REMINDER)

    def test_meeting_today_creates_notification_for_host(self):
        now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
        self.meeting_repository.meetings.append(_Meeting(uuid4(), self.user.id, datetime(2026, 9, 27, 12, tzinfo=timezone.utc)))

        result = self.use_case.execute(now)

        self.assertEqual(result.meeting_notifications_created, 1)
        notification = next(iter(self.notification_repository.items.values()))
        self.assertEqual(notification.notification_type, NotificationType.MEETING_TODAY)
        self.assertEqual(notification.user_id, self.user.id)

    def test_scheduler_is_idempotent(self):
        now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
        self.task_repository.tasks.append(_Task(uuid4(), self.user.id, date(2026, 9, 27)))

        first = self.use_case.execute(now)
        second = self.use_case.execute(now)
        third = self.use_case.execute(now)

        self.assertEqual(first.task_notifications_created, 1)
        self.assertEqual(second.task_notifications_created, 0)
        self.assertEqual(third.task_notifications_created, 0)
        self.assertEqual(second.duplicates_skipped, 1)
        self.assertEqual(third.duplicates_skipped, 1)
        self.assertEqual(len(self.notification_repository.items), 1)
