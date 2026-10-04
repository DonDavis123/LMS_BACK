import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
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
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)


class UserDeleteFlowTestCase(APITestCase):

    def setUp(self):
        def make(email, name, role, **extra):
            return User.objects.create_user(
                email=email, password="password123", name=name, role=role, **extra,
            )

        self.superadmin = make("superadmin@example.com", "Super Admin", User.Role.SUPERADMIN)
        self.target = make("target@example.com", "Target User", User.Role.ADMIN)
        self.replacement = make("replacement@example.com", "Replacement", User.Role.ADMIN)
        self.admin = make("admin@example.com", "Admin", User.Role.ADMIN)
        self.now = timezone.now()
        self.preview_url = f"/api/users/{self.target.id}/deletion-preview/"
        self.candidates_url = f"/api/users/{self.target.id}/replacement-candidates/"
        self.delete_url = f"/api/users/{self.target.id}/"
        self.make = make
        self.client.force_authenticate(self.superadmin)

    # ---------- helpers ----------

    def retire(self, replacement_id=None):
        body = {} if replacement_id is None else {"replacement_user_id": str(replacement_id)}
        return self.client.delete(self.delete_url, body, format="json")

    def assert_target_untouched(self):
        target = User.objects.get(id=self.target.id)
        self.assertIsNone(target.deleted_at)
        self.assertTrue(target.is_active)

    def lead(self):
        return DjangoLeadModel.objects.create(name="Lead", owner=self.target)

    def contact(self):
        return DjangoContactModel.objects.create(
            contact_owner=self.target, name="Contact",
            created_by=self.target, modified_by=self.target,
            created_at=self.now, updated_at=self.now,
        )

    def account(self):
        return DjangoAccountModel.objects.create(
            account_owner=self.target, account_name="Account",
            created_by=self.target, modified_by=self.target,
            created_at=self.now, updated_at=self.now,
        )

    def meeting(self):
        return DjangoMeetingModel.objects.create(
            title="Meeting", host=self.target, created_by=self.target,
            start_at=self.now, end_at=self.now + timedelta(hours=1),
        )

    def task(self):
        return DjangoTaskModel.objects.create(
            subject="Task", owner=self.target, created_by=self.target,
        )

    def reminder(self):
        return DjangoReminderModel.objects.create(
            subject="Reminder", remind_at=self.now + timedelta(days=1), user=self.target,
        )

    def notification(self):
        return DjangoNotificationModel.objects.create(
            notification_type="REMINDER", title="N", message="m", user=self.target,
            scheduled_for=self.now, expires_at=self.now + timedelta(days=1),
        )

    def timeline_event(self):
        DjangoTimelineRepository().record(
            event_type="LEAD_CREATED", actor_id=self.target.id,
            message="created", metadata={}, targets=[("LEAD", uuid.uuid4())],
        )


class DeletionPreviewExtensionTests(UserDeleteFlowTestCase):

    def test_preview_with_data(self):
        self.lead()
        self.task()

        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_related_data"])
        self.assertFalse(response.data["user_is_blocked"])
        self.assertEqual(response.data["available_actions"], ["BLOCK", "TRANSFER_AND_DELETE"])

    def test_preview_without_data(self):
        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["has_related_data"])
        self.assertFalse(response.data["user_is_blocked"])
        self.assertEqual(response.data["available_actions"], ["BLOCK", "TRANSFER_AND_DELETE"])

    def test_each_countable_record_sets_has_related_data(self):
        for create in (
            self.lead, self.contact, self.account, self.meeting,
            self.task, self.reminder, self.notification,
        ):
            with self.subTest(record=create.__name__):
                create()
                self.assertTrue(self.client.get(self.preview_url).data["has_related_data"])
                for model in (
                    DjangoLeadModel, DjangoContactModel, DjangoAccountModel,
                    DjangoMeetingModel, DjangoTaskModel, DjangoReminderModel,
                    DjangoNotificationModel,
                ):
                    model.objects.all().delete()

    def test_timeline_alone_is_not_related_data(self):
        self.timeline_event()

        response = self.client.get(self.preview_url)

        self.assertEqual(response.data["impact"]["timeline"], 1)
        self.assertFalse(response.data["has_related_data"])

    def test_blocked_target_does_not_offer_block(self):
        User.objects.filter(id=self.target.id).update(is_active=False)

        response = self.client.get(self.preview_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["user_is_blocked"])
        self.assertEqual(response.data["available_actions"], ["TRANSFER_AND_DELETE"])
        self.assertTrue(response.data["can_retire"])

    def test_self_target_offers_no_actions(self):
        response = self.client.get(f"/api/users/{self.superadmin.id}/deletion-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_retire"])
        self.assertEqual(response.data["available_actions"], [])

    def test_existing_preview_fields_are_unchanged(self):
        response = self.client.get(self.preview_url)

        self.assertTrue(
            {
                "user", "impact", "transfer_required", "permanent_deletions",
                "user_action", "can_retire", "blockers",
            }.issubset(response.data)
        )
        self.assertEqual(response.data["user_action"], {"type": "SOFT_DELETE"})


class ReplacementCandidatesTests(UserDeleteFlowTestCase):

    def emails(self, response):
        return [item["email"] for item in response.data]

    def test_lists_active_admins_and_superadmins_excluding_target(self):
        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            sorted(self.emails(response)),
            ["admin@example.com", "replacement@example.com", "superadmin@example.com"],
        )
        self.assertNotIn(self.target.email, self.emails(response))

    def test_item_shape(self):
        response = self.client.get(self.candidates_url)

        item = next(i for i in response.data if i["email"] == "replacement@example.com")
        self.assertEqual(
            item,
            {
                "id": str(self.replacement.id),
                "name": "Replacement",
                "email": "replacement@example.com",
                "role": "ADMIN",
            },
        )

    def test_excludes_blocked_users(self):
        User.objects.filter(id=self.admin.id).update(is_active=False)

        self.assertNotIn("admin@example.com", self.emails(self.client.get(self.candidates_url)))

    def test_excludes_deleted_users(self):
        User.objects.filter(id=self.admin.id).update(deleted_at=timezone.now())

        self.assertNotIn("admin@example.com", self.emails(self.client.get(self.candidates_url)))

    def test_excludes_non_admin_roles(self):
        self.make("manager@example.com", "Manager", User.Role.SALES_MANAGER)
        self.make("executive@example.com", "Executive", User.Role.SALES_EXECUTIVE)

        emails = self.emails(self.client.get(self.candidates_url))

        self.assertNotIn("manager@example.com", emails)
        self.assertNotIn("executive@example.com", emails)

    def test_blocked_target_still_has_candidates(self):
        User.objects.filter(id=self.target.id).update(is_active=False)

        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("replacement@example.com", self.emails(response))

    def test_unknown_target_returns_404(self):
        response = self.client.get(f"/api/users/{uuid.uuid4()}/replacement-candidates/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_target_returns_400(self):
        User.objects.filter(id=self.target.id).update(
            deleted_at=timezone.now(), is_active=False,
        )

        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "User has already been deleted.")

    def test_admin_is_forbidden(self):
        self.client.force_authenticate(self.admin)

        self.assertEqual(
            self.client.get(self.candidates_url).status_code, status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_is_unauthorized(self):
        self.client.force_authenticate(None)

        self.assertEqual(
            self.client.get(self.candidates_url).status_code, status.HTTP_401_UNAUTHORIZED,
        )

    def test_lead_owners_endpoint_is_unchanged(self):
        response = self.client.get("/api/lead-owners/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("target@example.com", [item["email"] for item in response.data])
        self.assertEqual(set(response.data[0]), {"id", "name", "email"})


class OptionalReplacementTests(UserDeleteFlowTestCase):

    def test_retire_without_replacement_when_nothing_to_transfer(self):
        self.task()
        self.reminder()
        self.notification()
        self.timeline_event()

        response = self.retire()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        target = User.objects.get(id=self.target.id)
        self.assertIsNotNone(target.deleted_at)
        self.assertFalse(target.is_active)
        self.assertEqual(DjangoTaskModel.objects.filter(owner=self.target).count(), 0)
        self.assertEqual(DjangoReminderModel.objects.filter(user=self.target).count(), 0)
        self.assertEqual(DjangoNotificationModel.objects.filter(user=self.target).count(), 0)
        self.assertEqual(
            DjangoTimelineRepository().count_by_actor_id(self.target.id), 1,
        )
        self.assertEqual(
            DjangoUserAuditLogModel.objects.filter(action="USER_RETIRED").count(), 1,
        )

    def test_retire_without_replacement_with_no_data_at_all(self):
        self.assertEqual(self.retire().status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNotNone(User.objects.get(id=self.target.id).deleted_at)

    def test_null_replacement_behaves_like_missing(self):
        response = self.client.delete(
            self.delete_url, {"replacement_user_id": None}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_missing_replacement_with_each_record_type_is_400_and_changes_nothing(self):
        for create in (self.lead, self.contact, self.account, self.meeting):
            with self.subTest(record=create.__name__):
                record = create()
                task = self.task()

                response = self.retire()

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data["detail"], "Replacement user is required.")
                self.assert_target_untouched()
                self.assertTrue(DjangoTaskModel.objects.filter(id=task.id).exists())
                self.assertEqual(DjangoUserAuditLogModel.objects.count(), 0)
                record.delete()
                task.delete()

    def test_missing_replacement_keeps_sessions_and_data(self):
        lead = self.lead()
        reminder = self.reminder()

        self.assertEqual(self.retire().status_code, status.HTTP_400_BAD_REQUEST)

        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.target.id)
        self.assertTrue(DjangoReminderModel.objects.filter(id=reminder.id).exists())

    def test_supplied_replacement_is_validated_even_with_nothing_to_transfer(self):
        self.admin.is_active = False
        self.admin.save()
        deleted = self.make("gone@example.com", "Gone", User.Role.ADMIN)
        User.objects.filter(id=deleted.id).update(
            deleted_at=timezone.now(), is_active=False,
        )
        manager = self.make("manager@example.com", "Manager", User.Role.SALES_MANAGER)

        cases = {
            "unknown": (uuid.uuid4(), status.HTTP_404_NOT_FOUND),
            "inactive": (self.admin.id, status.HTTP_400_BAD_REQUEST),
            "deleted": (deleted.id, status.HTTP_400_BAD_REQUEST),
            "self": (self.target.id, status.HTTP_400_BAD_REQUEST),
            "role": (manager.id, status.HTTP_400_BAD_REQUEST),
        }
        for label, (replacement_id, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(self.retire(replacement_id).status_code, expected)
                self.assert_target_untouched()

    def test_malformed_replacement_still_400(self):
        response = self.client.delete(
            self.delete_url, {"replacement_user_id": "nope"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retire_with_replacement_still_transfers(self):
        lead = self.lead()
        meeting = self.meeting()

        response = self.retire(self.replacement.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        lead.refresh_from_db()
        meeting.refresh_from_db()
        self.assertEqual(lead.owner_id, self.replacement.id)
        self.assertEqual(meeting.host_id, self.replacement.id)

    def test_supplied_replacement_without_data_is_recorded_in_audit(self):
        self.assertEqual(self.retire(self.replacement.id).status_code, 204)

        entry = DjangoUserAuditLogModel.objects.get(action="USER_RETIRED")
        self.assertEqual(entry.metadata["replacement_user_email"], self.replacement.email)

    def test_self_delete_is_still_rejected(self):
        response = self.client.delete(f"/api/users/{self.superadmin.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNone(User.objects.get(id=self.superadmin.id).deleted_at)

    def test_admin_is_forbidden_and_unauthenticated_is_unauthorized(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.retire().status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)
        self.assertEqual(self.retire().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_target_untouched()

    def test_database_failure_without_replacement_is_generic_500_and_rolls_back(self):
        task = self.task()
        reminder = self.reminder()

        with patch(
            "src.modules.users.infrastructure.persistence.user_repository."
            "DjangoUserRepository.soft_delete",
            side_effect=DatabaseError("sensitive db detail"),
        ):
            response = self.retire()

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"detail": "User could not be deleted."})
        self.assertTrue(DjangoTaskModel.objects.filter(id=task.id).exists())
        self.assertTrue(DjangoReminderModel.objects.filter(id=reminder.id).exists())
        self.assert_target_untouched()
        self.assertEqual(DjangoUserAuditLogModel.objects.count(), 0)
