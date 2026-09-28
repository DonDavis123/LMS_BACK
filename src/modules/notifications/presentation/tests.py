from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from src.modules.reminders.infrastructure.persistence.models.django_reminder_model import DjangoReminderModel

from src.modules.notifications.domain.entities.notification import Notification
from src.modules.notifications.domain.enums.notification_type import NotificationType
from src.modules.notifications.infrastructure.persistence.django_notification_repository import DjangoNotificationRepository


class NotificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email=f"notification-api-{uuid4()}@example.com",
            password="test-password",
            name="Notification API User",
        )
        self.other_user = get_user_model().objects.create_user(
            email=f"notification-api-other-{uuid4()}@example.com",
            password="test-password",
            name="Other User",
        )
        self.repository = DjangoNotificationRepository()
        self.client.force_authenticate(user=self.user)

    def _create(self, user_id, *, is_read=False, expires_at=None):
        notification = Notification.create(
            notification_type=NotificationType.REMINDER,
            title="Reminder",
            message="Call customer",
            user_id=user_id,
            scheduled_for=timezone.now() - timedelta(minutes=1),
        )
        if is_read:
            notification.mark_as_read()
        saved = self.repository.save(notification)
        if expires_at is not None:
            from src.modules.notifications.infrastructure.persistence.models import DjangoNotificationModel
            DjangoNotificationModel.objects.filter(id=saved.id).update(
                expires_at=expires_at,
                created_at=expires_at - timedelta(days=1),
            )
        return saved

    def test_list_returns_only_current_user_active_notifications(self):
        own = self._create(self.user.id)
        self._create(self.other_user.id)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [str(own.id)])

    def test_unauthenticated_list_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, 401)

    def test_unread_endpoint_excludes_read_notifications(self):
        unread = self._create(self.user.id)
        self._create(self.user.id, is_read=True)

        response = self.client.get("/api/notifications/unread/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [str(unread.id)])

    def test_cross_user_retrieve_is_rejected(self):
        other = self._create(self.other_user.id)
        response = self.client.get(f"/api/notifications/{other.id}/")
        self.assertEqual(response.status_code, 404)

    def test_mark_read(self):
        notification = self._create(self.user.id)
        response = self.client.patch(
            f"/api/notifications/{notification.id}/",
            {"is_read": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

    def test_cross_user_mark_read_is_rejected(self):
        other = self._create(self.other_user.id)
        response = self.client.patch(
            f"/api/notifications/{other.id}/",
            {"is_read": True},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_own_notification(self):
        notification = self._create(self.user.id)
        response = self.client.delete(f"/api/notifications/{notification.id}/")
        self.assertEqual(response.status_code, 200)
        dismissed = self.repository.get_by_id(notification.id)
        self.assertIsNotNone(dismissed)
        self.assertIsNotNone(dismissed.dismissed_at)

    def test_cross_user_delete_is_rejected(self):
        other = self._create(self.other_user.id)
        response = self.client.delete(f"/api/notifications/{other.id}/")
        self.assertEqual(response.status_code, 404)

class NotificationCronEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email=f"notification-cron-{uuid4()}@example.com",
            password="test-password",
            name="Notification Cron User",
        )
        self.secret = "test-cron-secret"
        self.cron_url = "/api/internal/notifications/process/"
        self.repository = DjangoNotificationRepository()

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_valid_cron_secret_processes_notifications(self):
        reminder = DjangoReminderModel.objects.create(
            subject="Call customer",
            remind_at=timezone.now() - timedelta(minutes=1),
            user=self.user,
        )

        response = self.client.post(
            self.cron_url,
            HTTP_X_CRON_SECRET=self.secret,
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "processed")
        self.assertEqual(response.data["reminders_processed"], 1)
        self.assertEqual(response.data["reminders_deleted"], 1)
        self.assertEqual(response.data["failures"], 0)

        self.assertFalse(
            DjangoReminderModel.objects.filter(id=reminder.id).exists()
        )

        notification = self.repository.get_by_user(self.user.id)[0]
        self.assertIsNone(notification.reminder_id)
        self.assertEqual(notification.user_id, self.user.id)

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_repeated_cron_processing_consumes_reminder_only_once(self):
        reminder = DjangoReminderModel.objects.create(
            subject="Call customer",
            remind_at=timezone.now() - timedelta(minutes=1),
            user=self.user,
        )

        first = self.client.post(
            self.cron_url,
            HTTP_X_CRON_SECRET=self.secret,
        )
        second = self.client.post(
            self.cron_url,
            HTTP_X_CRON_SECRET=self.secret,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["reminders_processed"], 1)
        self.assertEqual(first.data["reminders_deleted"], 1)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["reminders_processed"], 0)
        self.assertEqual(second.data["reminders_deleted"], 0)
        self.assertEqual(len(self.repository.get_by_user(self.user.id)), 1)
        self.assertFalse(
            DjangoReminderModel.objects.filter(id=reminder.id).exists()
        )

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_processing_failure_keeps_due_reminder(self):
        reminder = DjangoReminderModel.objects.create(
            subject="Call customer",
            remind_at=timezone.now() - timedelta(minutes=1),
            user=self.user,
        )

        with patch(
            "src.modules.notifications.presentation.api.views.notification_cron.ProcessNotificationsUseCase.execute",
            side_effect=RuntimeError("processing failed"),
        ):
            response = self.client.post(
                self.cron_url,
                HTTP_X_CRON_SECRET=self.secret,
            )

        self.assertEqual(response.status_code, 500)
        self.assertTrue(
            DjangoReminderModel.objects.filter(id=reminder.id).exists()
        )

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_missing_cron_secret_is_rejected(self):
        response = self.client.post(self.cron_url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid cron credentials.")

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_invalid_cron_secret_is_rejected(self):
        response = self.client.post(
            self.cron_url,
            HTTP_X_CRON_SECRET="wrong-secret",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid cron credentials.")

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_jwt_authentication_without_cron_secret_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.cron_url)

        self.assertEqual(response.status_code, 401)

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_get_is_rejected(self):
        response = self.client.get(
            self.cron_url,
            HTTP_X_CRON_SECRET=self.secret,
        )

        self.assertEqual(response.status_code, 405)

    @override_settings(NOTIFICATION_CRON_SECRET=None)
    def test_missing_server_secret_fails_closed(self):
        response = self.client.post(
            self.cron_url,
            HTTP_X_CRON_SECRET=self.secret,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid cron credentials.")

    @override_settings(NOTIFICATION_CRON_SECRET="test-cron-secret")
    def test_processing_exception_returns_generic_500(self):
        with patch(
            "src.modules.notifications.presentation.api.views.notification_cron.ProcessNotificationsUseCase.execute",
            side_effect=RuntimeError("database credentials leaked if returned"),
        ):
            response = self.client.post(
                self.cron_url,
                HTTP_X_CRON_SECRET=self.secret,
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data["detail"],
            "Notification processing failed.",
        )
        self.assertNotIn("database credentials", str(response.data))
