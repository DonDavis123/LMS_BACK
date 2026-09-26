from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from src.modules.reminders.domain.entities.reminder import Reminder
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from src.modules.reminders.infrastructure.persistence.models import DjangoReminderModel


class ReminderDomainTests(TestCase):
    def test_create_standalone_reminder(self):
        reminder = Reminder.create(
            subject="Call customer",
            remind_at=timezone.now() + timedelta(hours=1),
            user_id=uuid4(),
        )

        self.assertIsNotNone(reminder.id)
        self.assertEqual(reminder.subject, "Call customer")
        self.assertIsNone(reminder.task_id)
        self.assertIsNone(reminder.meeting_id)

    def test_subject_is_required(self):
        with self.assertRaises(ValueError):
            Reminder.create(
                subject="   ",
                remind_at=timezone.now(),
                user_id=uuid4(),
            )

    def test_remind_at_is_required(self):
        with self.assertRaises(ValueError):
            Reminder.create(
                subject="Call customer",
                remind_at=None,
                user_id=uuid4(),
            )

    def test_task_and_meeting_cannot_both_be_set(self):
        with self.assertRaises(ValueError):
            Reminder.create(
                subject="Invalid reminder",
                remind_at=timezone.now(),
                user_id=uuid4(),
                task_id=uuid4(),
                meeting_id=uuid4(),
            )


class ReminderRepositoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=f"reminder-{uuid4()}",
            password="test-password",
        )
        self.repository = DjangoReminderRepository()

    def test_save_and_get_by_id(self):
        reminder = Reminder.create(
            subject="Follow up",
            remind_at=timezone.now() + timedelta(hours=1),
            user_id=self.user.id,
        )

        saved = self.repository.save(reminder)
        found = self.repository.get_by_id(saved.id)

        self.assertIsNotNone(found)
        self.assertEqual(found.id, saved.id)
        self.assertEqual(found.subject, "Follow up")
        self.assertEqual(found.user_id, self.user.id)

    def test_get_by_user(self):
        reminder = Reminder.create(
            subject="User reminder",
            remind_at=timezone.now() + timedelta(hours=1),
            user_id=self.user.id,
        )
        self.repository.save(reminder)

        reminders = self.repository.get_by_user(self.user.id)

        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, reminder.id)

    def test_get_due(self):
        due = Reminder.create(
            subject="Due reminder",
            remind_at=timezone.now() - timedelta(minutes=1),
            user_id=self.user.id,
        )
        future = Reminder.create(
            subject="Future reminder",
            remind_at=timezone.now() + timedelta(hours=1),
            user_id=self.user.id,
        )
        self.repository.save(due)
        self.repository.save(future)

        reminders = self.repository.get_due(timezone.now())

        self.assertEqual([item.id for item in reminders], [due.id])

    def test_delete_by_id(self):
        reminder = Reminder.create(
            subject="Delete me",
            remind_at=timezone.now() + timedelta(hours=1),
            user_id=self.user.id,
        )
        self.repository.save(reminder)

        self.assertTrue(self.repository.delete_by_id(reminder.id))
        self.assertFalse(
            DjangoReminderModel.objects.filter(id=reminder.id).exists()
        )
