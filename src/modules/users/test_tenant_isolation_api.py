import uuid

from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
    token_client,
)
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)
from src.modules.users.infrastructure.persistence.user_audit_log_repository import (
    DjangoUserAuditLogRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


class TwoCompaniesTestCase(APITestCase):

    def setUp(self):
        self.company_a = make_company("Company A", "company-a")
        self.company_b = make_company("Company B", "company-b")

        self.superadmin_a = make_user(
            self.company_a, User.Role.SUPERADMIN, "super-a@example.com",
        )
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "admin-a@example.com")
        self.other_a = make_user(self.company_a, User.Role.ADMIN, "other-a@example.com")

        self.superadmin_b = make_user(
            self.company_b, User.Role.SUPERADMIN, "super-b@example.com",
        )
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "admin-b@example.com")
        self.other_b = make_user(self.company_b, User.Role.ADMIN, "other-b@example.com")

        self.platform = make_user(
            None, User.Role.PLATFORM_SUPERADMIN, "platform@example.com",
        )

        self.client_a = authenticated_client(self.superadmin_a)
        self.client_b = authenticated_client(self.superadmin_b)

    def audit(self, **filters):
        return DjangoUserAuditLogModel.objects.filter(**filters)

    def assert_not_found(self, response):
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserReadIsolationTests(TwoCompaniesTestCase):

    def test_list_only_returns_own_company_users(self):
        response = self.client_a.get("/api/users/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.data["results"]}
        self.assertEqual(
            emails,
            {"super-a@example.com", "admin-a@example.com", "other-a@example.com"},
        )
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_list_search_and_filters_never_reach_other_companies(self):
        for params in (
            {"search": "admin-b"},
            {"search": "example.com", "page_size": 50},
            {"filters": '[{"field":"email","operator":"contains","value":"-b@"}]'},
        ):
            with self.subTest(params=params):
                response = self.client_a.get("/api/users/", params)
                if response.status_code == status.HTTP_200_OK:
                    emails = {row["email"] for row in response.data["results"]}
                    self.assertFalse(
                        any(email.endswith("-b@example.com") for email in emails),
                    )

    def test_detail_of_other_company_user_is_404(self):
        self.assert_not_found(self.client_a.get(f"/api/users/{self.admin_b.id}/"))

    def test_detail_of_own_company_user_works(self):
        response = self.client_a.get(f"/api/users/{self.admin_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "admin-a@example.com")

    def test_foreign_user_404_matches_unknown_user_404(self):
        foreign = self.client_a.get(f"/api/users/{self.admin_b.id}/")
        unknown = self.client_a.get(f"/api/users/{uuid.uuid4()}/")

        self.assertEqual(foreign.status_code, unknown.status_code)
        self.assertEqual(foreign.data, unknown.data)

    def test_lead_owners_only_returns_own_company(self):
        response = self.client_a.get("/api/lead-owners/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.data}
        self.assertEqual(
            emails,
            {"super-a@example.com", "admin-a@example.com", "other-a@example.com"},
        )

    def test_replacement_candidates_only_returns_own_company(self):
        response = self.client_a.get(
            f"/api/users/{self.admin_a.id}/replacement-candidates/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.data}
        self.assertEqual(emails, {"super-a@example.com", "other-a@example.com"})

    def test_replacement_candidates_of_other_company_user_is_404(self):
        self.assert_not_found(
            self.client_a.get(f"/api/users/{self.admin_b.id}/replacement-candidates/"),
        )

    def test_deletion_preview_of_other_company_user_is_404(self):
        self.assert_not_found(
            self.client_a.get(f"/api/users/{self.admin_b.id}/deletion-preview/"),
        )

    def test_deletion_preview_of_own_company_user_works(self):
        response = self.client_a.get(f"/api/users/{self.admin_a.id}/deletion-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserWriteIsolationTests(TwoCompaniesTestCase):

    def test_update_other_company_user_is_404_and_changes_nothing(self):
        response = self.client_a.patch(
            f"/api/users/{self.admin_b.id}/",
            {"name": "Hacked", "email": "hacked@example.com"},
            format="json",
        )

        self.assert_not_found(response)
        self.admin_b.refresh_from_db()
        self.assertEqual(self.admin_b.email, "admin-b@example.com")
        self.assertNotEqual(self.admin_b.name, "Hacked")
        self.assertFalse(self.audit(target_user_id=self.admin_b.id).exists())

    def test_block_other_company_user_is_404_and_changes_nothing(self):
        self.assert_not_found(
            self.client_a.post(f"/api/users/{self.admin_b.id}/block/"),
        )

        self.admin_b.refresh_from_db()
        self.assertTrue(self.admin_b.is_active)
        self.assertFalse(self.audit(target_user_id=self.admin_b.id).exists())

    def test_unblock_other_company_user_is_404_and_changes_nothing(self):
        self.admin_b.is_active = False
        self.admin_b.save(update_fields=["is_active"])

        self.assert_not_found(
            self.client_a.post(f"/api/users/{self.admin_b.id}/unblock/"),
        )

        self.admin_b.refresh_from_db()
        self.assertFalse(self.admin_b.is_active)

    def test_reset_password_of_other_company_user_is_404_and_changes_nothing(self):
        response = self.client_a.post(
            f"/api/users/{self.admin_b.id}/reset-password/",
            {"new_password": "brandnewpass1"},
            format="json",
        )

        self.assert_not_found(response)
        self.admin_b.refresh_from_db()
        self.assertTrue(self.admin_b.check_password("password123"))
        self.assertFalse(self.audit(target_user_id=self.admin_b.id).exists())

    def test_delete_other_company_user_is_404_and_changes_nothing(self):
        response = self.client_a.delete(
            f"/api/users/{self.admin_b.id}/",
            {"replacement_user_id": str(self.admin_a.id)},
            format="json",
        )

        self.assert_not_found(response)
        self.admin_b.refresh_from_db()
        self.assertIsNone(self.admin_b.deleted_at)
        self.assertTrue(self.admin_b.is_active)

    def test_delete_with_replacement_from_other_company_behaves_like_unknown(self):
        foreign = self.client_a.delete(
            f"/api/users/{self.admin_a.id}/",
            {"replacement_user_id": str(self.admin_b.id)},
            format="json",
        )
        unknown = self.client_a.delete(
            f"/api/users/{self.admin_a.id}/",
            {"replacement_user_id": str(uuid.uuid4())},
            format="json",
        )

        self.assertEqual(foreign.status_code, unknown.status_code)
        self.assertEqual(foreign.data, unknown.data)
        self.admin_a.refresh_from_db()
        self.assertIsNone(self.admin_a.deleted_at)

    def test_delete_only_transfers_leads_of_own_company(self):
        own_lead = DjangoLeadModel.objects.create(
            name="Own", owner=self.admin_a, company=self.company_a,
        )
        foreign_lead = DjangoLeadModel.objects.create(
            name="Foreign", owner=self.admin_b, company=self.company_b,
        )

        response = self.client_a.delete(
            f"/api/users/{self.admin_a.id}/",
            {"replacement_user_id": str(self.other_a.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        own_lead.refresh_from_db()
        foreign_lead.refresh_from_db()
        self.assertEqual(own_lead.owner_id, self.other_a.id)
        self.assertEqual(foreign_lead.owner_id, self.admin_b.id)
        self.assertEqual(foreign_lead.company_id, self.company_b.id)

    def test_own_company_user_can_still_be_managed(self):
        self.assertEqual(
            self.client_a.post(f"/api/users/{self.admin_a.id}/block/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client_a.post(f"/api/users/{self.admin_a.id}/unblock/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client_a.patch(
                f"/api/users/{self.admin_a.id}/", {"name": "Renamed"}, format="json",
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client_a.post(
                f"/api/users/{self.admin_a.id}/reset-password/",
                {"new_password": "brandnewpass1"},
                format="json",
            ).status_code,
            status.HTTP_204_NO_CONTENT,
        )


class UserCreationTenancyTests(TwoCompaniesTestCase):

    def _create(self, client, email="new@example.com", **extra):
        return client.post(
            "/api/users/",
            {
                "name": "New",
                "email": email,
                "password": "newpassword123",
                "role": "ADMIN",
                **extra,
            },
            format="json",
        )

    def test_create_stamps_the_actors_company(self):
        response = self._create(self.client_a)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="new@example.com")
        self.assertEqual(created.company_id, self.company_a.id)

        response = self._create(self.client_b, email="new-b@example.com")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(email="new-b@example.com").company_id,
            self.company_b.id,
        )

    def test_company_in_the_request_body_is_ignored(self):
        response = self._create(
            self.client_a,
            company_id=str(self.company_b.id),
            company=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(email="new@example.com").company_id,
            self.company_a.id,
        )

    def test_company_in_query_string_and_header_is_ignored(self):
        response = self.client_a.post(
            f"/api/users/?company_id={self.company_b.id}",
            {
                "name": "New",
                "email": "new@example.com",
                "password": "newpassword123",
                "role": "ADMIN",
            },
            format="json",
            HTTP_X_COMPANY_ID=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(email="new@example.com").company_id,
            self.company_a.id,
        )

    def test_create_stamps_the_audit_log_company(self):
        self._create(self.client_a)

        entry = self.audit(action="USER_CREATED", target_email="new@example.com").get()
        self.assertEqual(entry.company_id, self.company_a.id)

    def test_create_still_rejects_roles_outside_manageable_roles(self):
        for role in ("SALES_MANAGER", "SALES_EXECUTIVE", "PLATFORM_SUPERADMIN"):
            with self.subTest(role=role):
                response = self.client_a.post(
                    "/api/users/",
                    {
                        "name": "New",
                        "email": f"{role.lower()}@example.com",
                        "password": "newpassword123",
                        "role": role,
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(
                    User.objects.filter(email=f"{role.lower()}@example.com").exists(),
                )

    def test_email_used_in_another_company_is_a_clean_400(self):
        response = self._create(self.client_a, email="admin-b@example.com")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "User with this email already exists.")
        self.assertEqual(User.objects.filter(email="admin-b@example.com").count(), 1)

    def test_email_used_in_own_company_gives_the_same_400(self):
        own = self._create(self.client_a, email="admin-a@example.com")
        foreign = self._create(self.client_a, email="admin-b@example.com")

        self.assertEqual(own.status_code, foreign.status_code)
        self.assertEqual(own.data, foreign.data)

    def test_update_email_to_another_companys_email_is_a_clean_400(self):
        response = self.client_a.patch(
            f"/api/users/{self.admin_a.id}/",
            {"email": "admin-b@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin_a.refresh_from_db()
        self.assertEqual(self.admin_a.email, "admin-a@example.com")

    def test_admin_still_cannot_create_users(self):
        response = self._create(authenticated_client(self.admin_a))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuditLogIsolationTests(TwoCompaniesTestCase):

    def test_audit_logs_only_contain_own_company_entries(self):
        self.client_a.post(f"/api/users/{self.admin_a.id}/block/")
        self.client_b.post(f"/api/users/{self.admin_b.id}/block/")

        response = self.client_a.get("/api/users/audit-logs/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        targets = {row["target_email"] for row in response.data["results"]}
        self.assertEqual(targets, {"admin-a@example.com"})
        self.assertEqual(response.data["pagination"]["total"], 1)

    def test_audit_logs_of_other_company_user_is_404(self):
        self.client_b.post(f"/api/users/{self.admin_b.id}/block/")

        response = self.client_a.get(
            "/api/users/audit-logs/", {"user_id": str(self.admin_b.id)},
        )

        self.assert_not_found(response)

    def test_audit_logs_of_unknown_user_gives_the_same_404(self):
        foreign = self.client_a.get(
            "/api/users/audit-logs/", {"user_id": str(self.admin_b.id)},
        )
        unknown = self.client_a.get(
            "/api/users/audit-logs/", {"user_id": str(uuid.uuid4())},
        )

        self.assertEqual(foreign.status_code, unknown.status_code)
        self.assertEqual(foreign.data, unknown.data)

    def test_audit_logs_of_own_company_user_work(self):
        self.client_a.post(f"/api/users/{self.admin_a.id}/block/")

        response = self.client_a.get(
            "/api/users/audit-logs/", {"user_id": str(self.admin_a.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 1)

    def test_audit_entries_are_stamped_with_the_actors_company(self):
        self.client_a.post(f"/api/users/{self.admin_a.id}/block/")
        self.client_b.post(f"/api/users/{self.admin_b.id}/block/")

        self.assertEqual(
            self.audit(target_user_id=self.admin_a.id).get().company_id,
            self.company_a.id,
        )
        self.assertEqual(
            self.audit(target_user_id=self.admin_b.id).get().company_id,
            self.company_b.id,
        )


class PlatformSuperadminTests(TwoCompaniesTestCase):

    def setUp(self):
        super().setUp()
        self.platform_client = authenticated_client(self.platform)

    def test_platform_superadmin_gets_403_on_every_company_endpoint(self):
        user_url = f"/api/users/{self.admin_a.id}/"
        requests = (
            ("get", "/api/users/", None),
            ("post", "/api/users/", {
                "name": "New", "email": "new@example.com",
                "password": "newpassword123", "role": "ADMIN",
            }),
            ("get", "/api/users/audit-logs/", None),
            ("get", user_url, None),
            ("patch", user_url, {"name": "Hacked"}),
            ("delete", user_url, {}),
            ("get", f"{user_url}deletion-preview/", None),
            ("get", f"{user_url}replacement-candidates/", None),
            ("post", f"{user_url}reset-password/", {"new_password": "brandnewpass1"}),
            ("post", f"{user_url}block/", None),
            ("post", f"{user_url}unblock/", None),
            ("get", "/api/lead-owners/", None),
        )

        for method, url, body in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.platform_client, method)(
                    url, body, format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.admin_a.refresh_from_db()
        self.assertTrue(self.admin_a.is_active)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_platform_superadmin_can_still_read_users_me(self):
        response = self.platform_client.get("/api/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "PLATFORM_SUPERADMIN")

    def test_company_users_me_still_works(self):
        response = self.client_a.get("/api/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "super-a@example.com")

    def test_jwt_platform_superadmin_gets_403(self):
        response = token_client(self.platform).get("/api/users/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_jwt_company_superadmin_is_allowed(self):
        response = token_client(self.superadmin_a).get("/api/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_company_superadmin_without_company_is_denied(self):
        orphan = make_user(None, User.Role.SUPERADMIN, "orphan@example.com")

        for method, url in (("get", "/api/users/"), ("get", "/api/lead-owners/")):
            with self.subTest(url=url):
                response = getattr(authenticated_client(orphan), method)(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_gets_401(self):
        from rest_framework.test import APIClient

        response = APIClient().get("/api/users/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserRepositoryScopingTests(TestCase):

    def setUp(self):
        self.company_a = make_company("Company A", "repo-a")
        self.company_b = make_company("Company B", "repo-b")
        self.user_a = make_user(self.company_a, User.Role.ADMIN, "a@example.com")
        self.user_b = make_user(self.company_b, User.Role.ADMIN, "b@example.com")
        self.repository_a = DjangoUserRepository(company_id=self.company_a.id)

    def test_get_by_id_get_by_email_and_lists_are_scoped(self):
        self.assertIsNotNone(self.repository_a.get_by_id(self.user_a.id))
        self.assertIsNone(self.repository_a.get_by_id(self.user_b.id))
        self.assertIsNone(self.repository_a.get_by_email("b@example.com"))
        self.assertEqual(
            [u.id for u in self.repository_a.get_lead_owners()],
            [self.user_a.id],
        )

    def test_mutations_cannot_reach_other_companies(self):
        self.assertIsNone(self.repository_a.set_active(self.user_b.id, False))
        self.assertIsNone(self.repository_a.set_password(self.user_b.id, "x12345678"))
        self.assertIsNone(
            self.repository_a.soft_delete(self.user_b.id, self.user_b.created_at),
        )
        self.user_b.refresh_from_db()
        self.assertTrue(self.user_b.is_active)
        self.assertIsNone(self.user_b.deleted_at)
        self.assertTrue(self.user_b.check_password("password123"))

    def test_update_of_other_company_user_raises_not_found(self):
        domain_user = DjangoUserRepository(company_id=self.company_b.id).get_by_id(
            self.user_b.id,
        )
        domain_user.name = "Hacked"

        with self.assertRaises(ValueError):
            self.repository_a.update(domain_user)

        self.user_b.refresh_from_db()
        self.assertNotEqual(self.user_b.name, "Hacked")

    def test_audit_log_repository_is_scoped(self):
        from src.modules.shared.application.dto.list_query import ListQuery
        from src.modules.users.domain.entities.user_audit_action import UserAuditAction
        from src.modules.users.domain.entities.user_audit_log import UserAuditLog

        repo_a = DjangoUserAuditLogRepository(company_id=self.company_a.id)
        repo_b = DjangoUserAuditLogRepository(company_id=self.company_b.id)
        domain_a = self.repository_a.get_by_id(self.user_a.id)
        domain_b = DjangoUserRepository(company_id=self.company_b.id).get_by_id(
            self.user_b.id,
        )
        repo_a.add(UserAuditLog.create(UserAuditAction.USER_BLOCKED, domain_a, domain_a))
        repo_b.add(UserAuditLog.create(UserAuditAction.USER_BLOCKED, domain_b, domain_b))

        query = ListQuery(page=1, page_size=50)

        self.assertEqual(repo_a.get_all(query).total, 1)
        self.assertEqual(repo_b.get_all(query).total, 1)
        self.assertEqual(
            repo_a.get_all(query, target_user_id=self.user_b.id).total, 0,
        )


class RepositoryRequiresCompanyTests(SimpleTestCase):

    def test_company_id_is_required(self):
        for repository in (DjangoUserRepository, DjangoUserAuditLogRepository):
            with self.subTest(repository=repository.__name__):
                with self.assertRaises(TypeError):
                    repository()
                with self.assertRaises(ValueError):
                    repository(company_id=None)
