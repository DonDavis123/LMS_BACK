import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.authentication.domain.exceptions import InvalidRefreshTokenError
from src.modules.authentication.infrastructure.security.jwt_token_service import (
    JWTTokenService,
)
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)
from src.modules.users.infrastructure.persistence.models import User


class UserManagementApiTestCase(APITestCase):

    def setUp(self):
        def make(email, name, role):
            return User.objects.create_user(
                email=email, password="password123", name=name, role=role,
            )

        self.superadmin = make("superadmin@example.com", "Super Admin", User.Role.SUPERADMIN)
        self.admin = make("admin@example.com", "Admin", User.Role.ADMIN)
        self.target = make("target@example.com", "Target User", User.Role.ADMIN)
        self.client.force_authenticate(self.superadmin)

    def audit(self, **filters):
        return DjangoUserAuditLogModel.objects.filter(**filters)


class SuperadminCreationTests(UserManagementApiTestCase):

    def _create(self, role, email="new@example.com"):
        return self.client.post(
            "/api/users/",
            {"name": "New", "email": email, "password": "newpassword123", "role": role},
            format="json",
        )

    def test_superadmin_can_create_another_superadmin(self):
        response = self._create(User.Role.SUPERADMIN)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], User.Role.SUPERADMIN)
        self.assertTrue(
            self.audit(action="USER_CREATED", target_email="new@example.com").exists()
        )

    def test_new_superadmin_can_manage_users(self):
        self._create(User.Role.SUPERADMIN)
        new_superadmin = User.objects.get(email="new@example.com")
        self.client.force_authenticate(new_superadmin)

        response = self.client.post(f"/api/users/{self.target.id}/block/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_create_superadmin(self):
        self.client.force_authenticate(self.admin)

        response = self._create(User.Role.SUPERADMIN)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_sales_roles_are_not_assignable(self):
        for role in (User.Role.SALES_MANAGER, User.Role.SALES_EXECUTIVE):
            with self.subTest(role=role):
                response = self._create(role, email=f"{role}@example.com".lower())
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_be_promoted_to_superadmin(self):
        response = self.client.patch(
            f"/api/users/{self.target.id}/", {"role": User.Role.SUPERADMIN}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.SUPERADMIN)

    def test_audit_failure_rolls_back_user_creation(self):
        with patch(
            "src.modules.users.infrastructure.persistence."
            "user_audit_log_repository.DjangoUserAuditLogRepository.add",
            side_effect=RuntimeError("boom"),
        ):
            self.client.raise_request_exception = False
            response = self._create(User.Role.ADMIN)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())


class AdminPasswordResetTests(UserManagementApiTestCase):

    def url(self, user=None):
        return f"/api/users/{(user or self.target).id}/reset-password/"

    def reset(self, password="brandnewpass1", user=None):
        return self.client.post(self.url(user), {"new_password": password}, format="json")

    def test_superadmin_resets_password(self):
        response = self.reset()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("brandnewpass1"))
        self.assertFalse(self.target.check_password("password123"))

    def test_user_can_login_with_new_password_only(self):
        self.reset()
        self.client.force_authenticate(None)

        new = self.client.post(
            "/api/auth/login/",
            {"email": "target@example.com", "password": "brandnewpass1"},
            format="json",
        )
        old = self.client.post(
            "/api/auth/login/",
            {"email": "target@example.com", "password": "password123"},
            format="json",
        )

        self.assertEqual(new.status_code, status.HTTP_200_OK)
        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reset_revokes_existing_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.target)

        self.reset()

        self.assertTrue(
            BlacklistedToken.objects.filter(token__user=self.target).exists()
        )
        with self.assertRaises(InvalidRefreshTokenError):
            JWTTokenService().refresh_access_token(str(refresh))

    def test_reset_is_audited_without_the_password(self):
        self.reset(password="supersecret99")

        entry = self.audit(action="USER_PASSWORD_RESET").get()
        self.assertEqual(entry.actor_id, self.superadmin.id)
        self.assertEqual(entry.target_user_id, self.target.id)
        self.assertNotIn("supersecret99", str(entry.metadata))
        self.assertNotIn("supersecret99", entry.target_email)

    def test_blocked_user_password_can_be_reset_and_stays_blocked(self):
        self.target.is_active = False
        self.target.save()

        self.assertEqual(self.reset().status_code, status.HTTP_204_NO_CONTENT)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_validation_and_error_cases(self):
        self.assertEqual(self.reset("short").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.post(self.url(), {}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                self.url(), {"new_password": "longenough1", "role": "SUPERADMIN"},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.url(), [{"a": 1}], format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.reset(user=self.superadmin).status_code, status.HTTP_400_BAD_REQUEST,
        )
        missing = self.client.post(
            f"/api/users/{uuid.uuid4()}/reset-password/",
            {"new_password": "longenough1"}, format="json",
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("password123"))
        self.assertFalse(self.audit(action="USER_PASSWORD_RESET").exists())

    def test_deleted_user_password_cannot_be_reset(self):
        self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)}, format="json",
        )

        self.assertEqual(self.reset().status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_superadmin_may_reset(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.reset().status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)
        self.assertEqual(self.reset().status_code, status.HTTP_401_UNAUTHORIZED)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("password123"))


class SessionRevocationTests(UserManagementApiTestCase):

    def _refresh_is_dead(self, refresh):
        with self.assertRaises(InvalidRefreshTokenError):
            JWTTokenService().refresh_access_token(str(refresh))

    def test_role_change_revokes_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.target)

        response = self.client.patch(
            f"/api/users/{self.target.id}/", {"role": User.Role.SUPERADMIN}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._refresh_is_dead(refresh)

    def test_role_change_takes_effect_for_existing_access_token(self):
        # Role is read from the database on every request, so an old access
        # token cannot keep admin privileges after a demotion.
        promoted = User.objects.create_user(
            email="promoted@example.com", password="password123",
            name="Promoted", role=User.Role.SUPERADMIN,
        )
        access = str(RefreshToken.for_user(promoted).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_200_OK)

        promoted.role = User.Role.ADMIN
        promoted.save()

        self.assertEqual(
            self.client.get("/api/users/").status_code, status.HTTP_403_FORBIDDEN,
        )

    def test_unchanged_role_does_not_revoke_sessions(self):
        refresh = RefreshToken.for_user(self.target)

        self.client.patch(
            f"/api/users/{self.target.id}/",
            {"name": "Renamed", "role": User.Role.ADMIN}, format="json",
        )

        self.assertFalse(BlacklistedToken.objects.filter(token__user=self.target).exists())
        self.assertTrue(OutstandingToken.objects.filter(user=self.target).exists())
        JWTTokenService().refresh_access_token(str(refresh))

    def test_block_revokes_refresh_tokens_so_unblock_does_not_revive_them(self):
        refresh = RefreshToken.for_user(self.target)

        self.client.post(f"/api/users/{self.target.id}/block/")
        self.client.post(f"/api/users/{self.target.id}/unblock/")

        self._refresh_is_dead(refresh)

    def test_retirement_revokes_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.target)

        response = self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self._refresh_is_dead(refresh)

    def test_other_users_sessions_are_untouched(self):
        other_refresh = RefreshToken.for_user(self.admin)

        self.client.patch(
            f"/api/users/{self.target.id}/", {"role": User.Role.SUPERADMIN}, format="json",
        )

        JWTTokenService().refresh_access_token(str(other_refresh))


class UserAuditLogTests(UserManagementApiTestCase):

    def test_actions_are_recorded_with_actor_target_and_details(self):
        self.client.post(
            "/api/users/",
            {"name": "New", "email": "new@example.com", "password": "newpassword123",
             "role": User.Role.ADMIN},
            format="json",
        )
        self.client.patch(
            f"/api/users/{self.target.id}/",
            {"name": "Renamed", "role": User.Role.SUPERADMIN}, format="json",
        )
        self.client.post(f"/api/users/{self.target.id}/block/")
        self.client.post(f"/api/users/{self.target.id}/unblock/")
        self.client.post(
            f"/api/users/{self.target.id}/reset-password/",
            {"new_password": "brandnewpass1"}, format="json",
        )
        self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)}, format="json",
        )

        actions = set(self.audit().values_list("action", flat=True))
        self.assertEqual(
            actions,
            {
                "USER_CREATED", "USER_UPDATED", "USER_ROLE_CHANGED", "USER_BLOCKED",
                "USER_UNBLOCKED", "USER_PASSWORD_RESET", "USER_RETIRED",
            },
        )
        for entry in self.audit():
            self.assertEqual(entry.actor_id, self.superadmin.id)
            self.assertEqual(entry.actor_email, "superadmin@example.com")

        role_change = self.audit(action="USER_ROLE_CHANGED").get()
        self.assertEqual(role_change.metadata, {"from": "ADMIN", "to": "SUPERADMIN"})
        retired = self.audit(action="USER_RETIRED").get()
        self.assertEqual(retired.metadata["replacement_user_id"], str(self.admin.id))
        updated = self.audit(action="USER_UPDATED").get()
        self.assertEqual(
            updated.metadata["changes"]["name"], {"from": "Target User", "to": "Renamed"},
        )

    def test_failed_actions_are_not_recorded(self):
        self.client.post(f"/api/users/{self.superadmin.id}/block/")
        self.client.patch(
            f"/api/users/{self.superadmin.id}/", {"role": User.Role.ADMIN}, format="json",
        )
        self.client.post(
            "/api/users/",
            {"name": "Dup", "email": "admin@example.com", "password": "newpassword123",
             "role": User.Role.ADMIN},
            format="json",
        )

        self.assertEqual(self.audit().count(), 0)

    def test_list_endpoint_with_filters_and_pagination(self):
        self.client.post(f"/api/users/{self.target.id}/block/")
        self.client.post(f"/api/users/{self.target.id}/unblock/")
        self.client.post(f"/api/users/{self.admin.id}/block/")

        everything = self.client.get("/api/users/audit-logs/")
        self.assertEqual(everything.status_code, status.HTTP_200_OK)
        self.assertEqual(everything.data["pagination"]["total"], 3)
        self.assertEqual(everything.data["results"][0]["action"], "USER_BLOCKED")
        self.assertEqual(
            everything.data["results"][0]["target_user_id"], str(self.admin.id),
        )

        for_target = self.client.get(f"/api/users/audit-logs/?user_id={self.target.id}")
        self.assertEqual(for_target.data["pagination"]["total"], 2)

        blocks = self.client.get("/api/users/audit-logs/?action=USER_BLOCKED")
        self.assertEqual(blocks.data["pagination"]["total"], 2)

        paged = self.client.get("/api/users/audit-logs/?page=1&page_size=2")
        self.assertEqual(len(paged.data["results"]), 2)
        self.assertEqual(paged.data["pagination"]["total_pages"], 2)

    def test_list_endpoint_validates_query(self):
        for query in ("user_id=not-a-uuid", "action=NOPE", "page_size=500"):
            with self.subTest(query=query):
                response = self.client.get(f"/api/users/audit-logs/?{query}")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_endpoint_is_superadmin_only(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get("/api/users/audit-logs/").status_code, status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get("/api/users/audit-logs/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_audit_entries_survive_user_retirement(self):
        self.client.post(f"/api/users/{self.target.id}/block/")
        self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)}, format="json",
        )

        response = self.client.get(f"/api/users/audit-logs/?user_id={self.target.id}")

        self.assertEqual(response.data["pagination"]["total"], 2)


class ReviewFixTests(UserManagementApiTestCase):

    def test_account_cannot_be_created_for_retired_or_blocked_user(self):
        self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)}, format="json",
        )
        self.admin.is_active = False
        self.admin.save()

        for owner in (self.target, self.admin):
            with self.subTest(owner=owner.email):
                response = self.client.post(
                    "/api/accounts/",
                    {"account_name": "Acme", "account_owner_id": str(owner.id)},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(DjangoAccountModel.objects.count(), 0)

    def test_account_with_unknown_owner_is_a_clean_400(self):
        response = self.client.post(
            "/api/accounts/",
            {"account_name": "Acme", "account_owner_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_defaults_to_current_user(self):
        response = self.client.post(
            "/api/accounts/", {"account_name": "Acme"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_object_bodies_are_400_not_500(self):
        url = f"/api/users/{self.target.id}/"
        for method in (self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                self.assertEqual(
                    method(url, [{"a": 1}], format="json").status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
