import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.authentication.domain.exceptions import InvalidRefreshTokenError
from src.modules.authentication.infrastructure.security.jwt_token_service import (
    JWTTokenService,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.infrastructure.persistence.models import DjangoMeetingModel
from src.modules.notifications.infrastructure.persistence.models import (
    DjangoNotificationModel,
)
from src.modules.reminders.infrastructure.persistence.models import DjangoReminderModel
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
from src.modules.users.infrastructure.persistence.models import User


class UserRetirementApiTests(APITestCase):

    def setUp(self):
        def make(email, name, role):
            return User.objects.create_user(
                email=email, password="password123", name=name, role=role,
            )

        self.superadmin = make("superadmin@example.com", "Super Admin", User.Role.SUPERADMIN)
        self.admin = make("admin@example.com", "Admin", User.Role.ADMIN)
        self.sales_manager = make("manager@example.com", "Manager", User.Role.SALES_MANAGER)
        self.sales_executive = make("executive@example.com", "Executive", User.Role.SALES_EXECUTIVE)
        self.target = make("target@example.com", "Target User", User.Role.ADMIN)
        self.replacement = make("replacement@example.com", "Replacement", User.Role.ADMIN)
        self.now = timezone.now()
        self.preview_url = f"/api/users/{self.target.id}/deletion-preview/"
        self.delete_url = f"/api/users/{self.target.id}/"

    # ---------- helpers ----------

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def retire(self, replacement_id=None, **kwargs):
        body = {} if replacement_id is None else {"replacement_user_id": str(replacement_id)}
        return self.client.delete(self.delete_url, body, format="json", **kwargs)

    def _assert_target_untouched(self):
        target = User.objects.get(id=self.target.id)
        self.assertIsNone(target.deleted_at)
        self.assertTrue(target.is_active)

    def _create_business_data(self):
        lead = DjangoLeadModel.objects.create(name="L1", owner=self.target)
        DjangoLeadModel.objects.create(name="L2", owner=self.target)
        account = DjangoAccountModel.objects.create(
            account_owner=self.target, account_name="A1",
            created_by=self.target, modified_by=self.target,
            created_at=self.now, updated_at=self.now,
        )
        for i in range(2):
            DjangoContactModel.objects.create(
                contact_owner=self.target, name=f"C{i}",
                created_by=self.target, modified_by=self.target,
                created_at=self.now, updated_at=self.now,
            )
        for i in range(2):
            DjangoTaskModel.objects.create(subject=f"T{i}", owner=self.target, created_by=self.target)
            DjangoMeetingModel.objects.create(
                title=f"M{i}", host=self.target, created_by=self.target,
                start_at=self.now, end_at=self.now + timedelta(hours=1),
            )
            DjangoReminderModel.objects.create(
                subject=f"R{i}", remind_at=self.now + timedelta(days=1), user=self.target,
            )
        for i in range(3):
            DjangoNotificationModel.objects.create(
                notification_type="REMINDER", title=f"N{i}", message="m", user=self.target,
                scheduled_for=self.now, expires_at=self.now + timedelta(days=1),
            )
        DjangoTimelineRepository().record(
            event_type="LEAD_CREATED", actor_id=self.target.id,
            message="created", metadata={}, targets=[("LEAD", lead.id)],
        )
        return lead, account

    # ---------- authorization ----------

    def test_non_superadmins_are_forbidden(self):
        for user in (self.admin, self.sales_manager, self.sales_executive):
            with self.subTest(role=user.role):
                self.authenticate(user)
                self.assertEqual(
                    self.client.get(self.preview_url).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.retire(self.replacement.id).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
        self._assert_target_untouched()

    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(self.preview_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.retire(self.replacement.id).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self._assert_target_untouched()

    # ---------- preview ----------

    def test_preview_returns_impact_for_superadmin(self):
        self._create_business_data()
        self.authenticate(self.superadmin)

        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["user"]["id"], str(self.target.id))
        self.assertEqual(data["user"]["email"], self.target.email)
        self.assertEqual(
            dict(data["impact"]),
            {
                "leads": 2, "contacts": 2, "accounts": 1, "tasks": 2,
                "meetings": 2, "reminders": 2, "notifications": 3, "timeline": 1,
            },
        )
        self.assertEqual(
            dict(data["transfer_required"]),
            {"leads": True, "contacts": True, "accounts": True, "meetings": True},
        )
        self.assertEqual(
            dict(data["permanent_deletions"]),
            {"tasks": 2, "reminders": 2, "notifications": 3},
        )
        self.assertEqual(data["user_action"], {"type": "SOFT_DELETE"})
        self.assertTrue(data["can_retire"])
        self.assertEqual(data["blockers"], [])
        self._assert_target_untouched()

    def test_preview_for_user_without_records(self):
        self.authenticate(self.superadmin)

        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(v == 0 for v in response.data["impact"].values()))
        self.assertFalse(any(response.data["transfer_required"].values()))
        self.assertTrue(response.data["can_retire"])

    def test_preview_for_self_cannot_retire(self):
        self.authenticate(self.superadmin)

        response = self.client.get(f"/api/users/{self.superadmin.id}/deletion-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_retire"])
        self.assertEqual(len(response.data["blockers"]), 1)

    def test_preview_missing_user_returns_404(self):
        self.authenticate(self.superadmin)
        response = self.client.get(f"/api/users/{uuid.uuid4()}/deletion-preview/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_of_deleted_user_returns_400(self):
        self.authenticate(self.superadmin)
        self.assertEqual(self.retire(self.replacement.id).status_code, 204)
        self.assertEqual(self.client.get(self.preview_url).status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- retire: validation ----------

    def test_missing_replacement_user_returns_400_when_records_must_be_transferred(self):
        self._create_business_data()
        self.authenticate(self.superadmin)
        response = self.retire()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Replacement user is required.")
        self._assert_target_untouched()

    def test_malformed_replacement_user_id_returns_400(self):
        self.authenticate(self.superadmin)
        response = self.client.delete(
            self.delete_url, {"replacement_user_id": "not-a-uuid"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_target_untouched()

    def test_unknown_body_fields_rejected(self):
        self.authenticate(self.superadmin)
        response = self.client.delete(
            self.delete_url,
            {"replacement_user_id": str(self.replacement.id), "role": "ADMIN"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_target_untouched()

    def test_replacement_user_not_found_returns_404(self):
        self.authenticate(self.superadmin)
        response = self.retire(uuid.uuid4())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self._assert_target_untouched()

    def test_inactive_replacement_returns_400(self):
        self.replacement.is_active = False
        self.replacement.save()
        self.authenticate(self.superadmin)
        response = self.retire(self.replacement.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_target_untouched()

    def test_soft_deleted_replacement_returns_400(self):
        self.replacement.deleted_at = timezone.now()
        self.replacement.is_active = False
        self.replacement.save()
        self.authenticate(self.superadmin)
        response = self.retire(self.replacement.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Replacement user has been deleted.")
        self._assert_target_untouched()

    def test_self_replacement_returns_400(self):
        self.authenticate(self.superadmin)
        response = self.retire(self.target.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_target_untouched()

    def test_replacement_with_invalid_role_returns_400(self):
        self.authenticate(self.superadmin)
        for user in (self.sales_manager, self.sales_executive):
            with self.subTest(role=user.role):
                self.assertEqual(
                    self.retire(user.id).status_code, status.HTTP_400_BAD_REQUEST,
                )
        self._assert_target_untouched()

    def test_target_user_not_found_returns_404(self):
        self.authenticate(self.superadmin)
        response = self.client.delete(
            f"/api/users/{uuid.uuid4()}/",
            {"replacement_user_id": str(self.replacement.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_already_deleted_target_returns_400(self):
        self.authenticate(self.superadmin)
        self.assertEqual(self.retire(self.replacement.id).status_code, 204)
        self.assertEqual(
            self.retire(self.replacement.id).status_code, status.HTTP_400_BAD_REQUEST,
        )

    def test_database_failure_returns_generic_500_and_changes_nothing(self):
        lead, _ = self._create_business_data()
        self.authenticate(self.superadmin)

        with patch(
            "src.modules.meetings.infrastructure.persistence."
            "django_meeting_repository.DjangoMeetingRepository.transfer_host",
            side_effect=DatabaseError("sensitive db detail"),
        ):
            response = self.retire(self.replacement.id)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"detail": "User could not be deleted."})
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.target.id)
        self.assertEqual(DjangoTaskModel.objects.filter(owner=self.target).count(), 2)
        self._assert_target_untouched()

    # ---------- full flow ----------

    def test_full_retirement_flow(self):
        lead, account = self._create_business_data()
        self.authenticate(self.superadmin)

        preview = self.client.get(self.preview_url)
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["impact"]["leads"], 2)
        self.assertEqual(preview.data["permanent_deletions"]["notifications"], 3)

        response = self.retire(self.replacement.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        target = User.objects.get(id=self.target.id)
        self.assertIsNotNone(target.deleted_at)
        self.assertFalse(target.is_active)

        self.assertEqual(DjangoLeadModel.objects.filter(owner=self.replacement).count(), 2)
        self.assertEqual(DjangoContactModel.objects.filter(contact_owner=self.replacement).count(), 2)
        self.assertEqual(DjangoAccountModel.objects.get(id=account.id).account_owner_id, self.replacement.id)
        self.assertEqual(DjangoAccountModel.objects.get(id=account.id).created_by_id, self.target.id)
        self.assertEqual(DjangoMeetingModel.objects.filter(host=self.replacement).count(), 2)
        self.assertEqual(DjangoMeetingModel.objects.count(), 2)
        self.assertFalse(DjangoTaskModel.objects.filter(owner=self.target).exists())
        self.assertFalse(DjangoReminderModel.objects.filter(user=self.target).exists())
        self.assertFalse(DjangoNotificationModel.objects.filter(user=self.target).exists())
        self.assertEqual(TimelineEvent.objects.filter(actor=self.target).count(), 1)

        # Retired user no longer offered anywhere as an active choice.
        listed = self.client.get("/api/users/?page_size=50").data["results"]
        self.assertNotIn(str(self.target.id), [u["id"] for u in listed])
        owners = self.client.get("/api/lead-owners/").data
        self.assertNotIn(str(self.target.id), [o["id"] for o in owners])

        # Not restorable through unblock.
        unblock = self.client.post(f"/api/users/{self.target.id}/unblock/")
        self.assertEqual(unblock.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.get(id=self.target.id).is_active)

    def test_retired_user_loses_api_access_and_cannot_refresh(self):
        refresh = RefreshToken.for_user(self.target)
        access = str(refresh.access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/users/me/").status_code, status.HTTP_200_OK)

        self.authenticate(self.superadmin)
        self.assertEqual(self.retire(self.replacement.id).status_code, 204)

        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(
            self.client.get("/api/users/me/").status_code, status.HTTP_401_UNAUTHORIZED,
        )
        with self.assertRaises(InvalidRefreshTokenError):
            JWTTokenService().refresh_access_token(str(refresh))

    def test_login_rejected_for_retired_user(self):
        self.authenticate(self.superadmin)
        self.assertEqual(self.retire(self.replacement.id).status_code, 204)
        self.client.force_authenticate(None)

        response = self.client.post(
            "/api/auth/login/",
            {"email": "target@example.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserApiRegressionTests(APITestCase):
    """Existing user endpoints keep their contracts."""

    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="superadmin@example.com", password="password123",
            name="Super Admin", role=User.Role.SUPERADMIN,
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="password123",
            name="Other", role=User.Role.ADMIN,
        )
        self.client.force_authenticate(self.superadmin)

    def test_existing_endpoints_still_work(self):
        created = self.client.post(
            "/api/users/",
            {"name": "New", "email": "new@example.com", "password": "newpassword123",
             "role": User.Role.ADMIN},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        new_id = created.data["id"]

        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f"/api/users/{new_id}/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.patch(f"/api/users/{new_id}/", {"name": "Renamed"}, format="json").status_code,
            status.HTTP_200_OK,
        )
        blocked = self.client.post(f"/api/users/{new_id}/block/")
        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertFalse(blocked.data["is_active"])
        unblocked = self.client.post(f"/api/users/{new_id}/unblock/")
        self.assertEqual(unblocked.status_code, status.HTTP_200_OK)
        self.assertTrue(unblocked.data["is_active"])
        me = self.client.get("/api/users/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["id"], str(self.superadmin.id))

    def test_blocked_user_can_still_be_retired_and_not_blocked_again(self):
        self.other.is_active = False
        self.other.save()
        replacement = User.objects.create_user(
            email="repl@example.com", password="password123",
            name="Repl", role=User.Role.ADMIN,
        )

        response = self.client.delete(
            f"/api/users/{self.other.id}/",
            {"replacement_user_id": str(replacement.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self.client.post(f"/api/users/{self.other.id}/block/").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
