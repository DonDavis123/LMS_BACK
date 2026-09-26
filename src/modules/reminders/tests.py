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


class _FakeReminderRepository:
    def __init__(self):
        self.items = {}

    def save(self, reminder):
        self.items[reminder.id] = reminder
        return reminder

    def get_by_id(self, reminder_id):
        return self.items.get(reminder_id)

    def get_by_user(self, user_id):
        return [
            reminder for reminder in self.items.values()
            if reminder.user_id == user_id
        ]

    def get_by_task(self, task_id):
        return [
            reminder for reminder in self.items.values()
            if reminder.task_id == task_id
        ]

    def get_by_meeting(self, meeting_id):
        return [
            reminder for reminder in self.items.values()
            if reminder.meeting_id == meeting_id
        ]

    def get_due(self, as_of):
        return [
            reminder for reminder in self.items.values()
            if reminder.remind_at <= as_of
        ]

    def delete_by_id(self, reminder_id):
        return self.items.pop(reminder_id, None) is not None


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


class _FakeTransactionManager:
    def execute(self, operation):
        return operation()


class ReminderApplicationTests(TestCase):
    def setUp(self):
        from src.modules.reminders.application.dto.create_reminder import (
            CreateReminderDTO,
        )
        from src.modules.reminders.application.dto.update_reminder import (
            UpdateReminderDTO,
        )
        from src.modules.reminders.application.use_cases.create_reminder import (
            CreateReminderUseCase,
        )
        from src.modules.reminders.application.use_cases.delete_reminder import (
            DeleteReminderUseCase,
        )
        from src.modules.reminders.application.use_cases.get_reminder import (
            GetReminderUseCase,
        )
        from src.modules.reminders.application.use_cases.get_reminders import (
            GetRemindersUseCase,
        )
        from src.modules.reminders.application.use_cases.update_reminder import (
            UpdateReminderUseCase,
        )

        self.CreateReminderDTO = CreateReminderDTO
        self.UpdateReminderDTO = UpdateReminderDTO
        self.CreateReminderUseCase = CreateReminderUseCase
        self.DeleteReminderUseCase = DeleteReminderUseCase
        self.GetReminderUseCase = GetReminderUseCase
        self.GetRemindersUseCase = GetRemindersUseCase
        self.UpdateReminderUseCase = UpdateReminderUseCase

        self.user_id = uuid4()
        self.other_user_id = uuid4()
        self.task_id = uuid4()
        self.meeting_id = uuid4()

        self.reminder_repository = _FakeReminderRepository()
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
        self.transaction_manager = _FakeTransactionManager()

    def _create_use_case(self):
        return self.CreateReminderUseCase(
            self.reminder_repository,
            self.user_repository,
            self.task_repository,
            self.meeting_repository,
            self.transaction_manager,
        )

    def test_create_standalone(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Call customer",
                remind_at=timezone.now() + timedelta(hours=1),
                user_id=self.user_id,
            )
        )

        self.assertEqual(reminder.user_id, self.user_id)
        self.assertIsNone(reminder.task_id)
        self.assertIsNone(reminder.meeting_id)

    def test_create_task_reminder(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Follow up",
                remind_at=timezone.now() + timedelta(hours=1),
                user_id=self.user_id,
                task_id=self.task_id,
            )
        )
        self.assertEqual(reminder.task_id, self.task_id)

    def test_create_meeting_reminder(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Meeting reminder",
                remind_at=timezone.now() + timedelta(hours=1),
                user_id=self.user_id,
                meeting_id=self.meeting_id,
            )
        )
        self.assertEqual(reminder.meeting_id, self.meeting_id)

    def test_create_rejects_missing_task(self):
        with self.assertRaisesMessage(ValueError, "Selected task not found."):
            self._create_use_case().execute(
                self.CreateReminderDTO(
                    subject="Invalid task",
                    remind_at=timezone.now(),
                    user_id=self.user_id,
                    task_id=uuid4(),
                )
            )

    def test_create_rejects_missing_meeting(self):
        with self.assertRaisesMessage(ValueError, "Selected meeting not found."):
            self._create_use_case().execute(
                self.CreateReminderDTO(
                    subject="Invalid meeting",
                    remind_at=timezone.now(),
                    user_id=self.user_id,
                    meeting_id=uuid4(),
                )
            )

    def test_create_rejects_both_targets(self):
        with self.assertRaisesMessage(
            ValueError,
            "A Reminder cannot be associated with both a Task and a Meeting.",
        ):
            self._create_use_case().execute(
                self.CreateReminderDTO(
                    subject="Invalid",
                    remind_at=timezone.now(),
                    user_id=self.user_id,
                    task_id=self.task_id,
                    meeting_id=self.meeting_id,
                )
            )

    def test_get_only_returns_owned_reminder(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Private",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )

        use_case = self.GetReminderUseCase(self.reminder_repository)
        self.assertIsNotNone(
            use_case.execute(reminder.id, current_user_id=self.user_id)
        )
        self.assertIsNone(
            use_case.execute(reminder.id, current_user_id=self.other_user_id)
        )

    def test_list_only_returns_owned_reminders(self):
        self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Mine",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )
        self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Other",
                remind_at=timezone.now(),
                user_id=self.other_user_id,
            )
        )

        reminders = self.GetRemindersUseCase(
            self.reminder_repository
        ).execute(self.user_id)

        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].subject, "Mine")

    def test_update_owned_reminder(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Old subject",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )

        updated = self.UpdateReminderUseCase(
            self.reminder_repository,
            self.task_repository,
            self.meeting_repository,
            self.transaction_manager,
        ).execute(
            self.UpdateReminderDTO(
                reminder_id=reminder.id,
                fields={"subject": "New subject", "task_id": self.task_id},
            ),
            current_user_id=self.user_id,
        )

        self.assertEqual(updated.subject, "New subject")
        self.assertEqual(updated.task_id, self.task_id)

    def test_update_rejects_other_owner(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Private",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )

        with self.assertRaisesMessage(ValueError, "Reminder not found."):
            self.UpdateReminderUseCase(
                self.reminder_repository,
                self.task_repository,
                self.meeting_repository,
                self.transaction_manager,
            ).execute(
                self.UpdateReminderDTO(
                    reminder_id=reminder.id,
                    fields={"subject": "Hijacked"},
                ),
                current_user_id=self.other_user_id,
            )

    def test_delete_owned_reminder(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Delete me",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )

        self.DeleteReminderUseCase(
            self.reminder_repository,
            self.transaction_manager,
        ).execute(
            reminder.id,
            current_user_id=self.user_id,
        )

        self.assertIsNone(self.reminder_repository.get_by_id(reminder.id))

    def test_delete_rejects_other_owner(self):
        reminder = self._create_use_case().execute(
            self.CreateReminderDTO(
                subject="Private",
                remind_at=timezone.now(),
                user_id=self.user_id,
            )
        )

        with self.assertRaisesMessage(ValueError, "Reminder not found."):
            self.DeleteReminderUseCase(
                self.reminder_repository,
                self.transaction_manager,
            ).execute(
                reminder.id,
                current_user_id=self.other_user_id,
            )


class ReminderAPITests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email=f"api-reminder-{uuid4()}@example.com",
            password="test-password",
            name="Reminder API User",
        )
        self.other_user = get_user_model().objects.create_user(
            email=f"api-reminder-other-{uuid4()}@example.com",
            password="test-password",
            name="Other User",
        )

    def _authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_unauthenticated_list_is_rejected(self):
        response = self.client.get("/api/reminders/")
        self.assertEqual(response.status_code, 401)

    def test_create_and_list_standalone_reminder(self):
        self._authenticate()

        response = self.client.post(
            "/api/reminders/",
            {
                "subject": "Call customer",
                "remind_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        reminder_id = response.data["id"]

        list_response = self.client.get("/api/reminders/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(str(list_response.data[0]["id"]), str(reminder_id))

    def test_get_update_delete_owned_reminder(self):
        self._authenticate()

        create_response = self.client.post(
            "/api/reminders/",
            {
                "subject": "Initial",
                "remind_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        reminder_id = create_response.data["id"]

        get_response = self.client.get(f"/api/reminders/{reminder_id}/")
        self.assertEqual(get_response.status_code, 200)

        update_response = self.client.patch(
            f"/api/reminders/{reminder_id}/",
            {"subject": "Updated"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["subject"], "Updated")

        delete_response = self.client.delete(
            f"/api/reminders/{reminder_id}/"
        )
        self.assertEqual(delete_response.status_code, 200)

        missing_response = self.client.get(
            f"/api/reminders/{reminder_id}/"
        )
        self.assertEqual(missing_response.status_code, 404)

    def test_other_user_cannot_access_reminder(self):
        self._authenticate()

        create_response = self.client.post(
            "/api/reminders/",
            {
                "subject": "Private",
                "remind_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        reminder_id = create_response.data["id"]

        self._authenticate(self.other_user)

        get_response = self.client.get(
            f"/api/reminders/{reminder_id}/"
        )
        self.assertEqual(get_response.status_code, 404)

        update_response = self.client.patch(
            f"/api/reminders/{reminder_id}/",
            {"subject": "Hijacked"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 400)

        delete_response = self.client.delete(
            f"/api/reminders/{reminder_id}/"
        )
        self.assertEqual(delete_response.status_code, 404)

        list_response = self.client.get("/api/reminders/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data, [])

    def test_create_rejects_both_targets_at_serializer_boundary(self):
        self._authenticate()

        response = self.client.post(
            "/api/reminders/",
            {
                "subject": "Invalid",
                "remind_at": (timezone.now() + timedelta(hours=1)).isoformat(),
                "task_id": str(uuid4()),
                "meeting_id": str(uuid4()),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
