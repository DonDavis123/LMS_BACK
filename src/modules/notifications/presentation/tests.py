from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

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
