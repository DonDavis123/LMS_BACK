"""End-to-end "Manage Users" flow, driven through the real HTTP API.

One superadmin logs in with a real JWT (no ``force_authenticate``) and walks
the whole Manage Users journey the frontend implements:

    me -> list/search/filter -> profile -> edit -> reset password ->
    block/unblock -> deletion preview -> replacement candidates -> delete

It then verifies the database side effects of retiring a user and that
ADMIN (403) and anonymous (401) callers are rejected on every endpoint.
"""

import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
)
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
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)


PASSWORD = "password123"
# Trailing space on purpose: passwords must be stored exactly as typed
# (login does not trim), so reset-password must not trim either.
NEW_PASSWORD = "NewPassw0rd! "
RENAMED_EMAIL = "renamed.target@example.com"


class ManageUsersFlowTests(APITestCase):

    def setUp(self):
        def make(email, name, role, **extra):
            return User.objects.create_user(
                email=email, password=PASSWORD, name=name, role=role, **extra,
            )

        self.superadmin = make("superadmin@example.com", "Super Admin", User.Role.SUPERADMIN)
        self.replacement = make("replacement@example.com", "Replacement Admin", User.Role.ADMIN)
        self.target = make("target@example.com", "Target User", User.Role.ADMIN)
        self.admin = make("admin@example.com", "Plain Admin", User.Role.ADMIN)
        # Stored with an upper-case local part (as created by createsuperuser,
        # the Django admin or an import); login treats e-mails case-insensitively.
        self.mixed = make("Mixed.Case@example.com", "Mixed Case", User.Role.ADMIN)
        self.blocked = make(
            "bob@example.com", "Blocked Bob", User.Role.SALES_MANAGER, is_active=False,
        )
        self.now = timezone.now()

    # ------------------------------------------------------------------ helpers

    def login(self, client, email, password):
        return client.post(
            "/api/auth/login/",
            {"email": email, "password": password},
            format="json",
        )

    def login_as(self, email, password=PASSWORD):
        client = APIClient()
        response = self.login(client, email, password)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access_token']}")
        return client

    @staticmethod
    def refresh_cookie(client):
        return client.cookies[settings.REFRESH_COOKIE_NAME].value

    def refresh_with(self, refresh_token):
        client = APIClient()
        client.cookies[settings.REFRESH_COOKIE_NAME] = refresh_token
        return client.post("/api/auth/refresh/")

    @staticmethod
    def call(client, method, url, body=None):
        if method == "get":  # APIClient.get takes query params, not a body
            return client.get(url)
        return getattr(client, method)(url, body, format="json")

    def audit(self, **filters):
        return DjangoUserAuditLogModel.objects.filter(
            target_user_id=self.target.id, **filters,
        )

    def assert_detail(self, response, expected_status, message):
        self.assertEqual(response.status_code, expected_status, response.content)
        self.assertEqual(response.data["detail"], message)

    def seed_target_data(self):
        """Everything the retired user can own, host, or be linked to."""
        t, a = self.target, self.admin
        self.leads = [
            DjangoLeadModel.objects.create(name="Lead 1", owner=t),
            DjangoLeadModel.objects.create(name="Lead 2", owner=t),
        ]
        self.contact = DjangoContactModel.objects.create(
            contact_owner=t, name="Contact",
            created_by=t, modified_by=t,
            created_at=self.now, updated_at=self.now,
        )
        self.account = DjangoAccountModel.objects.create(
            account_owner=t, account_name="Account",
            created_by=t, modified_by=t,
            created_at=self.now, updated_at=self.now,
        )
        self.task1 = DjangoTaskModel.objects.create(subject="Task 1", owner=t, created_by=t)
        self.task2 = DjangoTaskModel.objects.create(subject="Task 2", owner=t, created_by=t)
        # Owned by someone else but created by the retired user: must survive.
        self.foreign_task = DjangoTaskModel.objects.create(
            subject="Foreign task", owner=a, created_by=t,
        )
        self.reminders = [
            DjangoReminderModel.objects.create(
                subject="Standalone", remind_at=self.now + timedelta(days=1), user=t,
            ),
            DjangoReminderModel.objects.create(
                subject="On task", remind_at=self.now + timedelta(days=1),
                user=t, task=self.task1,
            ),
        ]
        self.notification = DjangoNotificationModel.objects.create(
            notification_type="REMINDER", title="N", message="m", user=t,
            scheduled_for=self.now, expires_at=self.now + timedelta(days=1),
        )
        self.foreign_notification = DjangoNotificationModel.objects.create(
            notification_type="REMINDER", title="N", message="m", user=a,
            scheduled_for=self.now, expires_at=self.now + timedelta(days=1),
        )
        window = {"start_at": self.now, "end_at": self.now + timedelta(hours=1)}
        self.hosted_meeting = DjangoMeetingModel.objects.create(
            title="Hosted", host=t, created_by=t, **window,
        )
        self.participant_meeting = DjangoMeetingModel.objects.create(
            title="Participant only", host=a, created_by=a, **window,
        )
        DjangoMeetingParticipantModel.objects.create(
            meeting=self.participant_meeting, participant_type="USER", user=t,
        )
        DjangoTimelineRepository().record(
            event_type="LEAD_CREATED", actor_id=t.id, message="created",
            metadata={}, targets=[("LEAD", self.leads[0].id)],
        )

    # --------------------------------------------------------------------- test

    def test_manage_users_flow_end_to_end(self):
        target_id = str(self.target.id)
        detail_url = f"/api/users/{target_id}/"

        # ---------------------------------------------------------------
        # k. ADMIN -> 403 and anonymous -> 401 on every user-management
        #    endpoint, and nothing is changed by the rejected calls.
        # ---------------------------------------------------------------
        endpoints = [
            ("get", "/api/users/", None),
            ("post", "/api/users/", {
                "name": "New", "email": "new@example.com",
                "password": "newpassword123", "role": "ADMIN",
            }),
            ("get", "/api/users/audit-logs/", None),
            ("get", detail_url, None),
            ("patch", detail_url, {"name": "Hacked"}),
            ("delete", detail_url, {"replacement_user_id": str(self.replacement.id)}),
            ("get", f"{detail_url}deletion-preview/", None),
            ("get", f"{detail_url}replacement-candidates/", None),
            ("post", f"{detail_url}reset-password/", {"new_password": "Hacked1234"}),
            ("post", f"{detail_url}block/", None),
            ("post", f"{detail_url}unblock/", None),
        ]
        users_before = User.objects.count()
        admin_client = self.login_as("admin@example.com")
        anonymous_client = APIClient()
        for method, url, body in endpoints:
            with self.subTest(endpoint=f"{method.upper()} {url}"):
                forbidden = self.call(admin_client, method, url, body)
                self.assert_detail(
                    forbidden, status.HTTP_403_FORBIDDEN, "Only superadmins can manage users.",
                )
                unauthenticated = self.call(anonymous_client, method, url, body)
                self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(User.objects.count(), users_before)
        self.assertFalse(DjangoUserAuditLogModel.objects.exists())
        target = User.objects.get(id=self.target.id)
        self.assertEqual(target.name, "Target User")
        self.assertTrue(target.is_active)
        self.assertIsNone(target.deleted_at)

        # ---------------------------------------------------------------
        # a. GET /api/users/me/ -> role SUPERADMIN (dashboard shows the
        #    Manage Users button). Same endpoint tells an ADMIN apart.
        # ---------------------------------------------------------------
        sa = self.login_as("superadmin@example.com")

        me = sa.get("/api/users/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(
            dict(me.data),
            {
                "id": str(self.superadmin.id),
                "name": "Super Admin",
                "email": "superadmin@example.com",
                "role": "SUPERADMIN",
            },
        )
        self.assertEqual(admin_client.get("/api/users/me/").data["role"], "ADMIN")
        self.assertEqual(
            anonymous_client.get("/api/users/me/").status_code, status.HTTP_401_UNAUTHORIZED,
        )

        # ---------------------------------------------------------------
        # b. GET /api/users/ with search, filters, sorting and paging.
        # ---------------------------------------------------------------
        listing = sa.get("/api/users/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(
            listing.data["pagination"],
            {"page": 1, "page_size": 20, "total": 6, "total_pages": 1},
        )
        self.assertEqual(
            set(listing.data["results"][0]),
            {"id", "name", "email", "role", "is_active", "created_at"},
        )

        searched = sa.get("/api/users/", {"search": "target"})
        self.assertEqual([u["email"] for u in searched.data["results"]], ["target@example.com"])

        by_role = sa.get("/api/users/", {"filters": json.dumps(
            [{"field": "role", "operator": "equals", "value": "SUPERADMIN"}],
        )})
        self.assertEqual([u["email"] for u in by_role.data["results"]], ["superadmin@example.com"])

        blocked_only = sa.get("/api/users/", {"filters": json.dumps(
            [{"field": "is_active", "operator": "equals", "value": False}],
        )})
        self.assertEqual([u["email"] for u in blocked_only.data["results"]], ["bob@example.com"])
        self.assertFalse(blocked_only.data["results"][0]["is_active"])

        combined = sa.get("/api/users/", {
            "search": "admin",
            "filters": json.dumps([{"field": "role", "operator": "equals", "value": "ADMIN"}]),
        })
        self.assertEqual(
            sorted(u["email"] for u in combined.data["results"]),
            ["admin@example.com", "replacement@example.com"],
        )

        page_two = sa.get("/api/users/", {
            "page": 2, "page_size": 2, "sort_by": "name", "sort_direction": "asc",
        })
        self.assertEqual(
            [u["name"] for u in page_two.data["results"]],
            ["Plain Admin", "Replacement Admin"],
        )
        self.assertEqual(
            page_two.data["pagination"],
            {"page": 2, "page_size": 2, "total": 6, "total_pages": 3},
        )

        self.assert_detail(
            sa.get("/api/users/", {"filters": json.dumps(
                [{"field": "password", "operator": "equals", "value": "x"}],
            )}),
            status.HTTP_400_BAD_REQUEST,
            "Filtering is not supported for field 'password'.",
        )
        self.assert_detail(
            sa.get("/api/users/", {"page_size": 51}),
            status.HTTP_400_BAD_REQUEST,
            "Page size must be less than or equal to 50.",
        )

        # ---------------------------------------------------------------
        # c. GET /api/users/<id>/ (profile page).
        # ---------------------------------------------------------------
        profile = sa.get(detail_url)
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(profile.data),
            {"id", "name", "email", "role", "is_active", "created_at", "updated_at"},
        )
        self.assertEqual(profile.data["id"], target_id)
        self.assertEqual(profile.data["name"], "Target User")
        self.assertEqual(profile.data["email"], "target@example.com")
        self.assertEqual(profile.data["role"], "ADMIN")
        self.assertTrue(profile.data["is_active"])
        self.assert_detail(
            sa.get(f"/api/users/{uuid.uuid4()}/"), status.HTTP_404_NOT_FOUND, "User not found.",
        )

        # ---------------------------------------------------------------
        # d. PATCH name and email; duplicate email -> 400.
        # ---------------------------------------------------------------
        patched = sa.patch(
            detail_url,
            {"name": "Target Renamed", "email": "Renamed.Target@Example.com"},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.content)
        self.assertEqual(patched.data["name"], "Target Renamed")
        self.assertEqual(patched.data["email"], RENAMED_EMAIL)  # normalised to lower case

        for duplicate in (
            "admin@example.com",
            "ADMIN@example.com",          # case variant of an existing address
            "mixed.case@example.com",     # existing row stored as Mixed.Case@...
        ):
            with self.subTest(duplicate=duplicate):
                self.assert_detail(
                    sa.patch(detail_url, {"email": duplicate}, format="json"),
                    status.HTTP_400_BAD_REQUEST,
                    "User with this email already exists.",
                )
        self.assertIn("email", sa.patch(detail_url, {"email": "nope"}, format="json").data)
        self.assertEqual(
            sa.patch(detail_url, {}, format="json").data["non_field_errors"],
            ["At least one field is required for update."],
        )
        self.assertEqual(User.objects.get(id=self.target.id).email, RENAMED_EMAIL)

        updated_logs = self.audit(action="USER_UPDATED")
        self.assertEqual(updated_logs.count(), 1)  # failed PATCHes leave no trail
        self.assertEqual(
            updated_logs.get().metadata["changes"],
            {
                "name": {"from": "Target User", "to": "Target Renamed"},
                "email": {"from": "target@example.com", "to": RENAMED_EMAIL},
            },
        )

        # ---------------------------------------------------------------
        # e. POST reset-password: old password fails, new one works and the
        #    user's existing refresh token stops working.
        # ---------------------------------------------------------------
        target_client = APIClient()
        self.assertEqual(
            self.login(target_client, RENAMED_EMAIL, PASSWORD).status_code,
            status.HTTP_200_OK,
        )
        refresh_before_reset = self.refresh_cookie(target_client)

        self.assertIn(
            "new_password",
            sa.post(f"{detail_url}reset-password/", {"new_password": "short"}, format="json").data,
        )
        self.assert_detail(
            sa.post(
                f"/api/users/{self.superadmin.id}/reset-password/",
                {"new_password": NEW_PASSWORD}, format="json",
            ),
            status.HTTP_400_BAD_REQUEST,
            "Use the forgot-password flow to change your own password.",
        )

        reset = sa.post(
            f"{detail_url}reset-password/", {"new_password": NEW_PASSWORD}, format="json",
        )
        self.assertEqual(reset.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(reset.content, b"")

        old_login = self.login(APIClient(), RENAMED_EMAIL, PASSWORD)
        self.assert_detail(old_login, status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
        new_login = self.login(APIClient(), RENAMED_EMAIL, NEW_PASSWORD)
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assert_detail(
            self.refresh_with(refresh_before_reset),
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired refresh token.",
        )
        self.assertEqual(self.audit(action="USER_PASSWORD_RESET").count(), 1)

        # ---------------------------------------------------------------
        # f. block, then unblock.
        # ---------------------------------------------------------------
        target_client = APIClient()
        self.login(target_client, RENAMED_EMAIL, NEW_PASSWORD)
        refresh_before_block = self.refresh_cookie(target_client)

        self.assert_detail(
            sa.post(f"/api/users/{self.superadmin.id}/block/"),
            status.HTTP_400_BAD_REQUEST,
            "A superadmin cannot block their own account.",
        )
        blocked = sa.post(f"{detail_url}block/")
        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertFalse(blocked.data["is_active"])
        self.assert_detail(
            self.login(APIClient(), RENAMED_EMAIL, NEW_PASSWORD),
            status.HTTP_403_FORBIDDEN,
            "User account is inactive.",
        )
        self.assertEqual(
            self.refresh_with(refresh_before_block).status_code, status.HTTP_401_UNAUTHORIZED,
        )

        unblocked = sa.post(f"{detail_url}unblock/")
        self.assertEqual(unblocked.status_code, status.HTTP_200_OK)
        self.assertTrue(unblocked.data["is_active"])

        target_client = APIClient()
        relogin = self.login(target_client, RENAMED_EMAIL, NEW_PASSWORD)
        self.assertEqual(relogin.status_code, status.HTTP_200_OK)
        # A live refresh token (rotated once) that the deletion must kill.
        rotated = target_client.post("/api/auth/refresh/")
        self.assertEqual(rotated.status_code, status.HTTP_200_OK)
        target_access_token = rotated.data["access_token"]
        live_refresh_token = self.refresh_cookie(target_client)
        self.assertEqual(self.audit(action="USER_BLOCKED").count(), 1)
        self.assertEqual(self.audit(action="USER_UNBLOCKED").count(), 1)

        # ---------------------------------------------------------------
        # g. GET deletion-preview for a user with leads, contacts, an
        #    account, tasks, meetings (host + participant), reminders and
        #    notifications.
        # ---------------------------------------------------------------
        self.seed_target_data()
        participant_meeting_updated_at = (
            DjangoMeetingModel.objects.get(id=self.participant_meeting.id).updated_at
        )

        preview = sa.get(f"{detail_url}deletion-preview/")
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(
            preview.data,
            {
                "user": {"id": target_id, "name": "Target Renamed", "email": RENAMED_EMAIL},
                "impact": {
                    "leads": 2, "contacts": 1, "accounts": 1, "tasks": 2,
                    # Hosted meetings only: participating in one is not counted.
                    "meetings": 1, "reminders": 2, "notifications": 1, "timeline": 1,
                },
                "transfer_required": {
                    "leads": True, "contacts": True, "accounts": True, "meetings": True,
                },
                "permanent_deletions": {"tasks": 2, "reminders": 2, "notifications": 1},
                "user_action": {"type": "SOFT_DELETE"},
                "can_retire": True,
                "blockers": [],
                "has_related_data": True,
                "user_is_blocked": False,
                "available_actions": ["BLOCK", "TRANSFER_AND_DELETE"],
            },
        )

        # ---------------------------------------------------------------
        # h. GET replacement-candidates: active ADMIN/SUPERADMIN, not the
        #    user itself, not blocked, not sales roles; ordered by name.
        # ---------------------------------------------------------------
        candidates = sa.get(f"{detail_url}replacement-candidates/")
        self.assertEqual(candidates.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [c["email"] for c in candidates.data],
            [
                "Mixed.Case@example.com",
                "admin@example.com",
                "replacement@example.com",
                "superadmin@example.com",
            ],
        )
        self.assertEqual(set(candidates.data[0]), {"id", "name", "email", "role"})
        self.assertNotIn(target_id, [c["id"] for c in candidates.data])

        # ---------------------------------------------------------------
        # i. DELETE: rejected requests first (nothing may change), then the
        #    real one with replacement_user_id -> 204.
        # ---------------------------------------------------------------
        def delete(body=None, url=detail_url):
            return sa.delete(url, body, format="json")

        self.assert_detail(
            delete({}), status.HTTP_400_BAD_REQUEST, "Replacement user is required.",
        )
        self.assert_detail(
            delete({"replacement_user_id": target_id}),
            status.HTTP_400_BAD_REQUEST,
            "Replacement user must be different from the user being deleted.",
        )
        self.assert_detail(
            delete({"replacement_user_id": str(self.blocked.id)}),
            status.HTTP_400_BAD_REQUEST,
            "Replacement user must be active.",
        )
        self.assert_detail(
            delete({"replacement_user_id": str(uuid.uuid4())}),
            status.HTTP_404_NOT_FOUND,
            "Replacement user not found.",
        )
        self.assert_detail(
            delete({"replacement_user_id": str(self.replacement.id)},
                   url=f"/api/users/{self.superadmin.id}/"),
            status.HTTP_400_BAD_REQUEST,
            "A superadmin cannot delete their own account.",
        )
        self.assertIsNone(User.objects.get(id=self.target.id).deleted_at)
        self.assertEqual(DjangoLeadModel.objects.filter(owner=self.target).count(), 2)
        self.assertEqual(self.audit(action="USER_RETIRED").count(), 0)

        deleted = delete({"replacement_user_id": str(self.replacement.id)})
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT, deleted.content)
        self.assertEqual(deleted.content, b"")

        # ---------------------------------------------------------------
        # j. Verify the side effects.
        # ---------------------------------------------------------------
        # User row kept, soft-deleted and inactive.
        retired = User.objects.get(id=self.target.id)
        self.assertIsNotNone(retired.deleted_at)
        self.assertFalse(retired.is_active)

        # Ownership moved to the replacement.
        for lead in self.leads:
            self.assertEqual(DjangoLeadModel.objects.get(id=lead.id).owner_id, self.replacement.id)
        contact = DjangoContactModel.objects.get(id=self.contact.id)
        account = DjangoAccountModel.objects.get(id=self.account.id)
        self.assertEqual(contact.contact_owner_id, self.replacement.id)
        self.assertEqual(account.account_owner_id, self.replacement.id)
        # created_by / modified_by are history and stay untouched.
        for record in (contact, account):
            self.assertEqual(record.created_by_id, self.target.id)
            self.assertEqual(record.modified_by_id, self.target.id)

        # Hosted meeting moves; participant-only meeting is left alone.
        hosted = DjangoMeetingModel.objects.get(id=self.hosted_meeting.id)
        self.assertEqual(hosted.host_id, self.replacement.id)
        self.assertEqual(hosted.created_by_id, self.target.id)
        participant_meeting = DjangoMeetingModel.objects.get(id=self.participant_meeting.id)
        self.assertEqual(participant_meeting.host_id, self.admin.id)
        self.assertEqual(participant_meeting.updated_at, participant_meeting_updated_at)
        self.assertTrue(
            DjangoMeetingParticipantModel.objects.filter(
                meeting_id=self.participant_meeting.id, user_id=self.target.id,
            ).exists()
        )

        # Tasks, reminders and notifications of the user are gone (including
        # the reminder that hung off a deleted task); other people's survive.
        self.assertFalse(DjangoTaskModel.objects.filter(owner_id=self.target.id).exists())
        self.assertFalse(DjangoReminderModel.objects.filter(user_id=self.target.id).exists())
        self.assertFalse(DjangoNotificationModel.objects.filter(user_id=self.target.id).exists())
        foreign_task = DjangoTaskModel.objects.get(id=self.foreign_task.id)
        self.assertEqual(foreign_task.created_by_id, self.target.id)
        self.assertTrue(
            DjangoNotificationModel.objects.filter(id=self.foreign_notification.id).exists()
        )

        # Timeline is preserved.
        self.assertEqual(TimelineEvent.objects.filter(actor_id=self.target.id).count(), 1)

        # Audit trail (DB and API).
        retired_log = self.audit(action="USER_RETIRED").get()
        self.assertEqual(retired_log.actor_id, self.superadmin.id)
        self.assertEqual(retired_log.actor_email, "superadmin@example.com")
        self.assertEqual(retired_log.target_email, RENAMED_EMAIL)
        self.assertEqual(
            retired_log.metadata,
            {
                "replacement_user_id": str(self.replacement.id),
                "replacement_user_email": "replacement@example.com",
            },
        )
        for action in ("USER_UPDATED", "USER_PASSWORD_RESET", "USER_BLOCKED", "USER_UNBLOCKED"):
            self.assertEqual(self.audit(action=action).count(), 1, action)
        audit_api = sa.get("/api/users/audit-logs/", {"user_id": target_id})
        self.assertEqual(audit_api.status_code, status.HTTP_200_OK)
        self.assertEqual(audit_api.data["pagination"]["total"], 5)
        self.assertEqual(audit_api.data["results"][0]["action"], "USER_RETIRED")
        self.assertEqual(
            {log["action"] for log in audit_api.data["results"]},
            {
                "USER_UPDATED", "USER_PASSWORD_RESET", "USER_BLOCKED",
                "USER_UNBLOCKED", "USER_RETIRED",
            },
        )

        # Sessions: refresh token dead, every outstanding token blacklisted,
        # access token and login rejected.
        self.assert_detail(
            self.refresh_with(live_refresh_token),
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired refresh token.",
        )
        outstanding = OutstandingToken.objects.filter(user_id=self.target.id)
        self.assertTrue(outstanding.exists())
        self.assertFalse(outstanding.exclude(blacklistedtoken__isnull=False).exists())
        stale = APIClient()
        stale.credentials(HTTP_AUTHORIZATION=f"Bearer {target_access_token}")
        self.assertEqual(stale.get("/api/users/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.login(APIClient(), RENAMED_EMAIL, NEW_PASSWORD).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Absent from the list and from search; further changes are refused.
        after = sa.get("/api/users/")
        self.assertEqual(after.data["pagination"]["total"], 5)
        self.assertNotIn(target_id, [u["id"] for u in after.data["results"]])
        self.assertEqual(sa.get("/api/users/", {"search": "renamed"}).data["pagination"]["total"], 0)
        self.assertNotIn(
            target_id,
            [c["id"] for c in sa.get(
                f"/api/users/{self.replacement.id}/replacement-candidates/",
            ).data],
        )

        already = "User has already been deleted."
        self.assert_detail(delete({}), status.HTTP_400_BAD_REQUEST, already)
        self.assert_detail(
            sa.get(f"{detail_url}deletion-preview/"), status.HTTP_400_BAD_REQUEST, already,
        )
        self.assert_detail(
            sa.get(f"{detail_url}replacement-candidates/"), status.HTTP_400_BAD_REQUEST, already,
        )
        self.assert_detail(
            sa.patch(detail_url, {"name": "Again"}, format="json"),
            status.HTTP_400_BAD_REQUEST,
            "A deleted user cannot be updated.",
        )
        self.assert_detail(
            sa.post(f"{detail_url}block/"),
            status.HTTP_400_BAD_REQUEST,
            "A deleted user cannot be blocked.",
        )
        self.assert_detail(
            sa.post(f"{detail_url}unblock/"),
            status.HTTP_400_BAD_REQUEST,
            "A deleted user cannot be unblocked.",
        )
        self.assert_detail(
            sa.post(
                f"{detail_url}reset-password/", {"new_password": "Another1234"}, format="json",
            ),
            status.HTTP_400_BAD_REQUEST,
            "A deleted user's password cannot be reset.",
        )
        # The soft-deleted row is still readable by id (inactive).
        gone = sa.get(detail_url)
        self.assertEqual(gone.status_code, status.HTTP_200_OK)
        self.assertFalse(gone.data["is_active"])
