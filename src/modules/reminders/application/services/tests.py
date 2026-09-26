from datetime import timedelta
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone

from src.modules.reminders.application.services.reminder_sync_service import ReminderSyncService
from src.modules.reminders.domain.entities.reminder import Reminder


class FakeReminderRepository:
    def __init__(self):
        self.items = {}

    def save(self, reminder):
        self.items[reminder.id] = reminder
        return reminder

    def get_by_task(self, task_id):
        return [item for item in self.items.values() if item.task_id == task_id]

    def get_by_meeting(self, meeting_id):
        return [item for item in self.items.values() if item.meeting_id == meeting_id]

    def delete_by_id(self, reminder_id):
        return self.items.pop(reminder_id, None) is not None


class FakeTask:
    def __init__(self, task_id, subject, owner_id, reminder_at, is_deleted=False):
        self.id = task_id
        self.subject = subject
        self.owner_id = owner_id
        self.reminder_at = reminder_at
        self.is_deleted = is_deleted


class FakeMeeting:
    def __init__(self, meeting_id, title, host_id, reminder_at, is_deleted=False):
        self.id = meeting_id
        self.title = title
        self.host_id = host_id
        self.reminder_at = reminder_at
        self.is_deleted = is_deleted


class ReminderSyncServiceTests(SimpleTestCase):
    def setUp(self):
        self.repository = FakeReminderRepository()
        self.service = ReminderSyncService(self.repository)
        self.user_id = uuid4()

    def test_creates_task_reminder(self):
        task = FakeTask(
            uuid4(),
            "Call customer",
            self.user_id,
            timezone.now() + timedelta(hours=1),
        )

        self.service.sync_task(task)

        reminders = self.repository.get_by_task(task.id)
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].subject, task.subject)
        self.assertEqual(reminders[0].remind_at, task.reminder_at)
        self.assertEqual(reminders[0].user_id, task.owner_id)

    def test_updates_existing_task_reminder_without_duplicate(self):
        task = FakeTask(
            uuid4(),
            "Call customer",
            self.user_id,
            timezone.now() + timedelta(hours=1),
        )
        existing = Reminder.create(
            subject="Old subject",
            remind_at=timezone.now(),
            user_id=self.user_id,
            task_id=task.id,
        )
        self.repository.save(existing)

        task.subject = "Updated customer call"
        task.reminder_at = timezone.now() + timedelta(hours=2)

        self.service.sync_task(task)

        reminders = self.repository.get_by_task(task.id)
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, existing.id)
        self.assertEqual(reminders[0].subject, task.subject)
        self.assertEqual(reminders[0].remind_at, task.reminder_at)

    def test_deletes_task_reminder_when_reminder_is_removed(self):
        task = FakeTask(
            uuid4(),
            "Call customer",
            self.user_id,
            timezone.now() + timedelta(hours=1),
        )
        existing = Reminder.create(
            subject=task.subject,
            remind_at=task.reminder_at,
            user_id=self.user_id,
            task_id=task.id,
        )
        self.repository.save(existing)

        task.reminder_at = None
        self.service.sync_task(task)

        self.assertEqual(self.repository.get_by_task(task.id), [])

    def test_creates_meeting_reminder(self):
        meeting = FakeMeeting(
            uuid4(),
            "Client meeting",
            self.user_id,
            timezone.now() + timedelta(hours=1),
        )

        self.service.sync_meeting(meeting)

        reminders = self.repository.get_by_meeting(meeting.id)
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].subject, meeting.title)
        self.assertEqual(reminders[0].remind_at, meeting.reminder_at)
        self.assertEqual(reminders[0].user_id, meeting.host_id)

    def test_deletes_meeting_reminder_when_meeting_is_deleted(self):
        meeting = FakeMeeting(
            uuid4(),
            "Client meeting",
            self.user_id,
            timezone.now() + timedelta(hours=1),
        )
        existing = Reminder.create(
            subject=meeting.title,
            remind_at=meeting.reminder_at,
            user_id=self.user_id,
            meeting_id=meeting.id,
        )
        self.repository.save(existing)

        meeting.is_deleted = True
        self.service.sync_meeting(meeting)

        self.assertEqual(self.repository.get_by_meeting(meeting.id), [])
