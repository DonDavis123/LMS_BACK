from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from src.modules.notifications.application.dto.create_notification import (
    CreateNotificationDTO,
)
from src.modules.notifications.application.use_cases.create_notification import (
    CreateNotificationUseCase,
)
from src.modules.notifications.application.use_cases.delete_expired_notifications import (
    DeleteExpiredNotificationsUseCase,
)
from src.modules.notifications.application.use_cases.delete_notification import (
    DeleteNotificationUseCase,
)
from src.modules.notifications.application.use_cases.get_notification import (
    GetNotificationUseCase,
)
from src.modules.notifications.application.use_cases.get_notifications import (
    GetNotificationsUseCase,
)
from src.modules.notifications.application.use_cases.mark_notification_read import (
    MarkNotificationReadUseCase,
)
from src.modules.notifications.domain.entities.notification import (
    NOTIFICATION_RETENTION_DAYS,
    Notification,
)
from src.modules.notifications.domain.enums.notification_type import NotificationType
from src.modules.notifications.infrastructure.persistence.django_notification_repository import (
    DjangoNotificationRepository,
)
from src.modules.notifications.infrastructure.persistence.models import (
    DjangoNotificationModel,
)


class NotificationDomainTests(TestCase):
    def test_create_valid_notification(self):
        scheduled_for = timezone.now() + timedelta(hours=1)
        notification = Notification.create(
            notification_type=NotificationType.REMINDER,
            title="Task reminder",
            message="Call customer",
            user_id=uuid4(),
            scheduled_for=scheduled_for,
        )
        self.assertIsNotNone(notification.id)
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        self.assertEqual(
            notification.expires_at,
            notification.created_at + timedelta(days=NOTIFICATION_RETENTION_DAYS),
        )

    def test_empty_title_rejected(self):
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title=" ",
                message="Message",
                user_id=uuid4(),
                scheduled_for=timezone.now(),
            )

    def test_empty_message_rejected(self):
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title="Title",
                message=" ",
                user_id=uuid4(),
                scheduled_for=timezone.now(),
            )

    def test_missing_user_rejected(self):
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title="Title",
                message="Message",
                user_id=None,
                scheduled_for=timezone.now(),
            )

    def test_missing_scheduled_for_rejected(self):
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title="Title",
                message="Message",
                user_id=uuid4(),
                scheduled_for=None,
            )

    def test_naive_scheduled_for_rejected(self):
        from datetime import datetime
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title="Title",
                message="Message",
                user_id=uuid4(),
                scheduled_for=datetime(2026, 10, 10),
            )

    def test_task_and_meeting_rejected(self):
        with self.assertRaises(ValueError):
            Notification.create(
                notification_type=NotificationType.REMINDER,
                title="Title",
                message="Message",
                user_id=uuid4(),
                scheduled_for=timezone.now(),
                task_id=uuid4(),
                meeting_id=uuid4(),
            )

    def test_mark_as_read(self):
        notification = Notification.create(
            notification_type=NotificationType.REMINDER,
            title="Title",
            message="Message",
            user_id=uuid4(),
            scheduled_for=timezone.now(),
        )
        read_at = timezone.now()
        notification.mark_as_read(read_at)
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.read_at, read_at)

    def test_unread_cannot_have_read_at(self):
        notification = Notification.create(
            notification_type=NotificationType.REMINDER,
            title="Title",
            message="Message",
            user_id=uuid4(),
            scheduled_for=timezone.now(),
        )
        notification.read_at = timezone.now()
        with self.assertRaises(ValueError):
            notification.validate_state()

    def test_expiry_must_be_after_scheduled_time(self):
        notification = Notification.create(
            notification_type=NotificationType.REMINDER,
            title="Title",
            message="Message",
            user_id=uuid4(),
            scheduled_for=timezone.now(),
        )
        notification.expires_at = notification.scheduled_for
        with self.assertRaises(ValueError):
            notification.validate_state()


class NotificationRepositoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email=f"notification-{uuid4()}@example.com",
            password="test-password",
            name="Notification User",
        )
        self.repository = DjangoNotificationRepository()

    def _notification(self, **kwargs):
        defaults = {
            "notification_type": NotificationType.REMINDER,
            "title": "Task reminder",
            "message": "Call customer",
            "user_id": self.user.id,
            "scheduled_for": timezone.now() + timedelta(hours=1),
        }
        defaults.update(kwargs)
        return Notification.create(**defaults)

    def test_save_and_get_by_id(self):
        notification = self.repository.save(self._notification())
        found = self.repository.get_by_id(notification.id)
        self.assertEqual(found.id, notification.id)
        self.assertEqual(found.title, notification.title)

    def test_get_by_user(self):
        notification = self.repository.save(self._notification())
        self.assertEqual(
            [item.id for item in self.repository.get_by_user(self.user.id)],
            [notification.id],
        )

    def test_get_unread_by_user(self):
        notification = self.repository.save(self._notification())
        read = self._notification(
            title="Read",
            message="Already read",
            scheduled_for=timezone.now() + timedelta(hours=2),
        )
        read.mark_as_read()
        self.repository.save(read)
        self.assertEqual(
            [item.id for item in self.repository.get_unread_by_user(self.user.id)],
            [notification.id],
        )

    def test_get_active_excludes_expired(self):
        active = self.repository.save(self._notification())
        expired = self._notification(
            title="Expired",
            message="Expired notification",
            scheduled_for=timezone.now() - timedelta(hours=2),
        )
        expired.expires_at = timezone.now() - timedelta(minutes=1)
        self.repository.save(expired)

        ids = [
            item.id
            for item in self.repository.get_active_by_user(
                self.user.id,
                timezone.now(),
            )
        ]
        self.assertIn(active.id, ids)
        self.assertNotIn(expired.id, ids)

    def test_get_due_filters_expired(self):
        due = self._notification(
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )
        future = self._notification(
            title="Future",
            message="Future notification",
            scheduled_for=timezone.now() + timedelta(hours=1),
        )
        self.repository.save(due)
        self.repository.save(future)
        due_list = self.repository.get_due(timezone.now())
        self.assertEqual([item.id for item in due_list], [due.id])

    def test_existing_source_lookup_prevents_duplicates(self):
        scheduled_for = timezone.now() + timedelta(hours=1)
        notification = self.repository.save(
            self._notification(
                notification_type=NotificationType.TASK_DUE_TODAY,
                scheduled_for=scheduled_for,
            )
        )
        found = self.repository.get_existing_for_source(
            notification_type=NotificationType.TASK_DUE_TODAY,
            scheduled_for=scheduled_for,
            task_id=None,
            meeting_id=None,
            reminder_id=None,
        )
        self.assertEqual(found.id, notification.id)

    def test_source_lookup_distinguishes_types(self):
        scheduled_for = timezone.now() + timedelta(hours=1)
        first = self.repository.save(
            self._notification(
                notification_type=NotificationType.TASK_DUE_TODAY,
                scheduled_for=scheduled_for,
            )
        )
        found = self.repository.get_existing_for_source(
            notification_type=NotificationType.TASK_DUE_ONE_DAY,
            scheduled_for=scheduled_for,
        )
        self.assertIsNone(found)

    def test_delete_by_id(self):
        notification = self.repository.save(self._notification())
        self.assertTrue(self.repository.delete_by_id(notification.id))
        self.assertFalse(
            DjangoNotificationModel.objects.filter(id=notification.id).exists()
        )

    def test_delete_expired(self):
        expired = self._notification()
        expired.expires_at = timezone.now() - timedelta(minutes=1)
        self.repository.save(expired)
        self.assertEqual(
            self.repository.delete_expired(timezone.now()),
            1,
        )
        self.assertFalse(
            DjangoNotificationModel.objects.filter(id=expired.id).exists()
        )


class _FakeUser:
    def __init__(self, user_id, is_active=True):
        self.id = user_id
        self.is_active = is_active


class _FakeTask:
    def __init__(self, task_id):
        self.id = task_id
        self.is_deleted = False


class _FakeMeeting:
    def __init__(self, meeting_id):
        self.id = meeting_id
        self.is_deleted = False


class _FakeReminder:
    def __init__(self, reminder_id, user_id):
        self.id = reminder_id
        self.user_id = user_id


class _FakeNotificationRepository:
    def __init__(self):
        self.items = {}

    def save(self, notification):
        self.items[notification.id] = notification
        return notification

    def get_by_id(self, notification_id):
        return self.items.get(notification_id)

    def get_by_user(self, user_id):
        return [n for n in self.items.values() if n.user_id == user_id]

    def get_unread_by_user(self, user_id):
        return [
            n for n in self.items.values()
            if n.user_id == user_id and not n.is_read
        ]

    def get_active_by_user(self, user_id, as_of):
        return [
            n for n in self.items.values()
            if n.user_id == user_id and n.expires_at > as_of
        ]

    def get_due(self, as_of):
        return [
            n for n in self.items.values()
            if n.scheduled_for <= as_of and n.expires_at > as_of
        ]

    def get_existing_for_source(
        self, *, notification_type, scheduled_for,
        task_id=None, meeting_id=None, reminder_id=None,
    ):
        for n in self.items.values():
            if (
                n.notification_type == notification_type
                and n.scheduled_for == scheduled_for
                and n.task_id == task_id
                and n.meeting_id == meeting_id
                and n.reminder_id == reminder_id
            ):
                return n
        return None

    def delete_by_id(self, notification_id):
        return self.items.pop(notification_id, None) is not None

    def delete_expired(self, as_of):
        expired = [n.id for n in self.items.values() if n.expires_at <= as_of]
        for item_id in expired:
            del self.items[item_id]
        return len(expired)


class _FakeUserRepository:
    def __init__(self, users):
        self.users = users

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class _FakeTaskRepository:
    def __init__(self, tasks):
        self.tasks = tasks

    def get_by_id(self, task_id):
        return self.tasks.get(task_id)


class _FakeMeetingRepository:
    def __init__(self, meetings):
        self.meetings = meetings

    def get_by_id(self, meeting_id):
        return self.meetings.get(meeting_id)


class _FakeReminderRepository:
    def __init__(self, reminders):
        self.reminders = reminders

    def get_by_id(self, reminder_id):
        return self.reminders.get(reminder_id)


class _FakeTransactionManager:
    def execute(self, operation):
        return operation()


class NotificationApplicationTests(TestCase):
    def setUp(self):
        self.user_id = uuid4()
        self.other_user_id = uuid4()
        self.task_id = uuid4()
        self.meeting_id = uuid4()
        self.reminder_id = uuid4()

        self.notification_repository = _FakeNotificationRepository()
        self.user_repository = _FakeUserRepository({
            self.user_id: _FakeUser(self.user_id),
            self.other_user_id: _FakeUser(self.other_user_id),
        })
        self.task_repository = _FakeTaskRepository({
            self.task_id: _FakeTask(self.task_id),
        })
        self.meeting_repository = _FakeMeetingRepository({
            self.meeting_id: _FakeMeeting(self.meeting_id),
        })
        self.reminder_repository = _FakeReminderRepository({
            self.reminder_id: _FakeReminder(self.reminder_id, self.user_id),
        })
        self.transaction_manager = _FakeTransactionManager()

        self.create = CreateNotificationUseCase(
            self.notification_repository,
            self.user_repository,
            self.task_repository,
            self.meeting_repository,
            self.reminder_repository,
            self.transaction_manager,
        )

    def test_create(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Task reminder",
                message="Call customer",
                user_id=self.user_id,
                scheduled_for=timezone.now() + timedelta(hours=1),
                task_id=self.task_id,
                reminder_id=self.reminder_id,
            )
        )
        self.assertEqual(notification.task_id, self.task_id)
        self.assertEqual(notification.reminder_id, self.reminder_id)

    def test_create_is_idempotent_for_same_source(self):
        scheduled_for = timezone.now() + timedelta(hours=1)
        data = CreateNotificationDTO(
            notification_type=NotificationType.TASK_DUE_TODAY,
            title="Task due today",
            message="Call customer is due today.",
            user_id=self.user_id,
            scheduled_for=scheduled_for,
            task_id=self.task_id,
        )
        first = self.create.execute(data)
        second = self.create.execute(data)
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.notification_repository.items), 1)

    def test_invalid_user_rejected(self):
        with self.assertRaisesMessage(ValueError, "Notification user not found."):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.REMINDER,
                    title="Title",
                    message="Message",
                    user_id=uuid4(),
                    scheduled_for=timezone.now(),
                )
            )

    def test_inactive_user_rejected(self):
        inactive_id = uuid4()
        self.user_repository.users[inactive_id] = _FakeUser(inactive_id, False)
        with self.assertRaisesMessage(ValueError, "Notification user is inactive."):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.REMINDER,
                    title="Title",
                    message="Message",
                    user_id=inactive_id,
                    scheduled_for=timezone.now(),
                )
            )

    def test_invalid_task_rejected(self):
        with self.assertRaisesMessage(ValueError, "Selected task not found."):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.TASK_DUE_TODAY,
                    title="Title",
                    message="Message",
                    user_id=self.user_id,
                    scheduled_for=timezone.now(),
                    task_id=uuid4(),
                )
            )

    def test_invalid_meeting_rejected(self):
        with self.assertRaisesMessage(ValueError, "Selected meeting not found."):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.MEETING_TODAY,
                    title="Title",
                    message="Message",
                    user_id=self.user_id,
                    scheduled_for=timezone.now(),
                    meeting_id=uuid4(),
                )
            )

    def test_invalid_reminder_rejected(self):
        with self.assertRaisesMessage(ValueError, "Selected reminder not found."):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.REMINDER,
                    title="Title",
                    message="Message",
                    user_id=self.user_id,
                    scheduled_for=timezone.now(),
                    reminder_id=uuid4(),
                )
            )

    def test_reminder_owner_mismatch_rejected(self):
        other_reminder = uuid4()
        self.reminder_repository.reminders[other_reminder] = _FakeReminder(
            other_reminder,
            self.other_user_id,
        )
        with self.assertRaisesMessage(
            ValueError,
            "Selected reminder does not belong to the notification user.",
        ):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.REMINDER,
                    title="Title",
                    message="Message",
                    user_id=self.user_id,
                    scheduled_for=timezone.now(),
                    reminder_id=other_reminder,
                )
            )

    def test_task_and_meeting_rejected(self):
        with self.assertRaises(ValueError):
            self.create.execute(
                CreateNotificationDTO(
                    notification_type=NotificationType.REMINDER,
                    title="Title",
                    message="Message",
                    user_id=self.user_id,
                    scheduled_for=timezone.now(),
                    task_id=self.task_id,
                    meeting_id=self.meeting_id,
                )
            )

    def test_get_ownership(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Private",
                message="Private message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        use_case = GetNotificationUseCase(self.notification_repository)
        self.assertIsNotNone(use_case.execute(notification.id, self.user_id))
        self.assertIsNone(use_case.execute(notification.id, self.other_user_id))

    def test_list_active(self):
        use_case = GetNotificationsUseCase(self.notification_repository)
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Active",
                message="Active message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        self.assertEqual(
            [n.id for n in use_case.execute(self.user_id, as_of=timezone.now())],
            [notification.id],
        )

    def test_mark_read_ownership(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Private",
                message="Private message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        read = MarkNotificationReadUseCase(
            self.notification_repository,
            self.transaction_manager,
        ).execute(notification.id, self.user_id)
        self.assertTrue(read.is_read)
        self.assertIsNotNone(read.read_at)

    def test_mark_read_other_user_rejected(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Private",
                message="Private message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        with self.assertRaisesMessage(ValueError, "Notification not found."):
            MarkNotificationReadUseCase(
                self.notification_repository,
                self.transaction_manager,
            ).execute(notification.id, self.other_user_id)

    def test_delete_ownership(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Delete",
                message="Delete message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        DeleteNotificationUseCase(
            self.notification_repository,
            self.transaction_manager,
        ).execute(notification.id, self.user_id)
        self.assertIsNone(
            self.notification_repository.get_by_id(notification.id)
        )

    def test_delete_other_user_rejected(self):
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Private",
                message="Private message",
                user_id=self.user_id,
                scheduled_for=timezone.now(),
            )
        )
        with self.assertRaisesMessage(ValueError, "Notification not found."):
            DeleteNotificationUseCase(
                self.notification_repository,
                self.transaction_manager,
            ).execute(notification.id, self.other_user_id)

    def test_delete_expired(self):
        repository = _FakeNotificationRepository()
        notification = self.create.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Expired",
                message="Expired message",
                user_id=self.user_id,
                scheduled_for=timezone.now() - timedelta(hours=2),
            )
        )
        notification.expires_at = timezone.now() - timedelta(minutes=1)
        repository.save(notification)
        deleted = DeleteExpiredNotificationsUseCase(
            repository,
            self.transaction_manager,
        ).execute(timezone.now())
        self.assertEqual(deleted, 1)
