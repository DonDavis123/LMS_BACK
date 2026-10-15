from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
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

BASE = "/api/platform/companies/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"


def valid_payload(**overrides):
    payload = {
        "company_name": "Acme Corp",
        "website": "https://acme.example.com",
        "admin_name": "Alice Admin",
        "admin_email": "alice@acme.example.com",
        "admin_password": "s3cret-pass",
    }
    payload.update(overrides)
    return payload


class PlatformCompaniesApiTests(APITestCase):

    def setUp(self):
        self.platform_admin = make_user(
            None, role=User.Role.PLATFORM_SUPERADMIN, email="platform@example.com"
        )
        self.client = authenticated_client(self.platform_admin)

    def create_company(self, **overrides):
        return self.client.post(BASE, valid_payload(**overrides), format="json")

    # --- create -----------------------------------------------------------

    def test_create_makes_company_and_first_superadmin(self):
        response = self.create_company()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = DjangoCompanyModel.objects.get(id=response.data["company"]["id"])
        self.assertEqual(company.status, DjangoCompanyModel.Status.ACTIVE)
        self.assertEqual(company.slug, "acme-corp")
        self.assertEqual(company.created_by_id, self.platform_admin.id)

        admin = User.objects.get(email="alice@acme.example.com")
        self.assertEqual(admin.role, User.Role.SUPERADMIN)
        self.assertEqual(admin.company_id, company.id)
        self.assertEqual(response.data["admin"]["email"], "alice@acme.example.com")
        self.assertNotIn("password", response.data["admin"])

        self.assertTrue(
            DjangoUserAuditLogModel.objects.filter(
                company_id=company.id,
                target_user_id=admin.id,
                actor_id=self.platform_admin.id,
            ).exists()
        )

    def test_first_superadmin_can_log_in(self):
        self.create_company()

        response = APIClient().post(
            LOGIN,
            {"email": "alice@acme.example.com", "password": "s3cret-pass"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)

    def test_duplicate_email_in_another_company_is_rejected(self):
        other = make_company("Other")
        make_user(other, email="alice@acme.example.com")

        response = self.create_company()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "User with this email already exists."
        )
        self.assertFalse(DjangoCompanyModel.objects.filter(name="Acme Corp").exists())

    def test_duplicate_email_is_case_insensitive(self):
        make_user(make_company("Other"), email="alice@acme.example.com")

        response = self.create_company(admin_email="ALICE@Acme.Example.com")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_slug_clash_gets_a_suffix(self):
        first = self.create_company(admin_email="a1@example.com")
        second = self.create_company(admin_email="a2@example.com")
        third = self.create_company(
            company_name="ACME corp", admin_email="a3@example.com"
        )

        self.assertEqual(first.data["company"]["slug"], "acme-corp")
        self.assertEqual(second.data["company"]["slug"], "acme-corp-2")
        self.assertEqual(third.data["company"]["slug"], "acme-corp-3")

    def test_create_validates_input(self):
        for overrides in (
            {"admin_password": "short"},
            {"admin_email": "not-an-email"},
            {"company_name": ""},
            {"admin_name": ""},
            {"website": "not a url"},
        ):
            with self.subTest(overrides=overrides):
                response = self.create_company(**overrides)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_website_is_optional(self):
        payload = valid_payload()
        del payload["website"]

        response = self.client.post(BASE, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- list -------------------------------------------------------------

    def test_list_is_paginated_with_users_count(self):
        self.create_company()
        make_company("Beta Inc", status=DjangoCompanyModel.Status.SUSPENDED)

        response = self.client.get(BASE)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["pagination"],
            {"page": 1, "page_size": 20, "total": 2, "total_pages": 1},
        )
        by_name = {item["name"]: item for item in response.data["results"]}
        self.assertEqual(by_name["Acme Corp"]["users_count"], 1)
        self.assertEqual(by_name["Beta Inc"]["users_count"], 0)
        self.assertEqual(
            set(by_name["Acme Corp"]),
            {"id", "name", "slug", "website", "status", "created_at", "users_count"},
        )

    def test_list_search_status_and_ordering(self):
        make_company("Alpha")
        make_company("Bravo", status=DjangoCompanyModel.Status.SUSPENDED)
        make_company("Charlie")

        search = self.client.get(BASE, {"search": "brav"})
        self.assertEqual([c["name"] for c in search.data["results"]], ["Bravo"])

        suspended = self.client.get(BASE, {"status": "SUSPENDED"})
        self.assertEqual([c["name"] for c in suspended.data["results"]], ["Bravo"])

        ordered = self.client.get(
            BASE, {"sort_by": "name", "sort_direction": "desc"}
        )
        self.assertEqual(
            [c["name"] for c in ordered.data["results"]],
            ["Charlie", "Bravo", "Alpha"],
        )

        paged = self.client.get(BASE, {"page_size": 2, "page": 2, "sort_by": "name"})
        self.assertEqual([c["name"] for c in paged.data["results"]], ["Charlie"])
        self.assertEqual(paged.data["pagination"]["total_pages"], 2)

    def test_list_rejects_bad_query(self):
        for params in ({"status": "NOPE"}, {"sort_by": "nope"}, {"page": "0"}):
            with self.subTest(params=params):
                response = self.client.get(BASE, params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- detail / patch ---------------------------------------------------

    def test_detail_includes_superadmins(self):
        company_id = self.create_company().data["company"]["id"]
        make_user(DjangoCompanyModel.objects.get(id=company_id), role=User.Role.ADMIN)

        response = self.client.get(f"{BASE}{company_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["users_count"], 2)
        self.assertEqual(response.data["status"], "ACTIVE")
        self.assertEqual(response.data["status_reason"], "")
        self.assertEqual(len(response.data["superadmins"]), 1)
        self.assertEqual(
            set(response.data["superadmins"][0]), {"id", "name", "email", "is_active"}
        )

    def test_unknown_company_is_404(self):
        missing = "00000000-0000-0000-0000-000000000000"
        for method, url, body in (
            ("get", f"{BASE}{missing}/", None),
            ("patch", f"{BASE}{missing}/", {"name": "X"}),
            ("post", f"{BASE}{missing}/suspend/", {"reason": "why"}),
            ("post", f"{BASE}{missing}/activate/", None),
        ):
            with self.subTest(url=url):
                response = getattr(self.client, method)(url, body, format="json")
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.data, {"detail": "Company not found."})

    def test_patch_updates_name_and_website_but_not_slug(self):
        company_id = self.create_company().data["company"]["id"]

        response = self.client.patch(
            f"{BASE}{company_id}/",
            {"name": "Acme Renamed", "website": "https://new.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        company = DjangoCompanyModel.objects.get(id=company_id)
        self.assertEqual(company.name, "Acme Renamed")
        self.assertEqual(company.website, "https://new.example.com")
        self.assertEqual(company.slug, "acme-corp")

    def test_patch_requires_a_field(self):
        company_id = self.create_company().data["company"]["id"]

        response = self.client.patch(f"{BASE}{company_id}/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- suspend / activate ----------------------------------------------

    def test_suspend_requires_a_reason(self):
        company_id = self.create_company().data["company"]["id"]

        for body in ({}, {"reason": ""}, {"reason": "   "}):
            with self.subTest(body=body):
                response = self.client.post(
                    f"{BASE}{company_id}/suspend/", body, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(
            DjangoCompanyModel.objects.get(id=company_id).status,
            DjangoCompanyModel.Status.ACTIVE,
        )

    def test_suspend_and_activate_flow(self):
        company_id = self.create_company().data["company"]["id"]
        credentials = {"email": "alice@acme.example.com", "password": "s3cret-pass"}

        user_client = APIClient()
        login = user_client.post(LOGIN, credentials, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        user_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")
        self.assertEqual(user_client.get("/api/leads/").status_code, status.HTTP_200_OK)

        suspend = self.client.post(
            f"{BASE}{company_id}/suspend/", {"reason": "Unpaid invoice"}, format="json"
        )
        self.assertEqual(suspend.status_code, status.HTTP_200_OK)
        self.assertEqual(suspend.data["status"], "SUSPENDED")
        self.assertEqual(suspend.data["status_reason"], "Unpaid invoice")
        company = DjangoCompanyModel.objects.get(id=company_id)
        self.assertIsNotNone(company.status_changed_at)
        self.assertEqual(company.status_changed_by_id, self.platform_admin.id)

        # Already suspended.
        again = self.client.post(
            f"{BASE}{company_id}/suspend/", {"reason": "again"}, format="json"
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

        # The old access token is rejected by the tenant endpoints.
        blocked = user_client.get("/api/leads/")
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            blocked.data["detail"], "Your company account is suspended."
        )

        # Login is refused after the password check.
        denied = APIClient().post(LOGIN, credentials, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied.data["detail"], "Your company account is suspended.")
        wrong = APIClient().post(
            LOGIN, {**credentials, "password": "wrong-password"}, format="json"
        )
        self.assertEqual(wrong.status_code, status.HTTP_401_UNAUTHORIZED)

        # The refresh token issued before the suspension no longer works.
        refresh_client = APIClient()
        refresh_client.cookies[settings.REFRESH_COOKIE_NAME] = login.cookies[
            settings.REFRESH_COOKIE_NAME
        ].value
        self.assertEqual(
            refresh_client.post(REFRESH).status_code, status.HTTP_401_UNAUTHORIZED
        )

        # Activate restores access.
        activate = self.client.post(f"{BASE}{company_id}/activate/")
        self.assertEqual(activate.status_code, status.HTTP_200_OK)
        self.assertEqual(activate.data["status"], "ACTIVE")
        self.assertEqual(activate.data["status_reason"], "")

        already = self.client.post(f"{BASE}{company_id}/activate/")
        self.assertEqual(already.status_code, status.HTTP_400_BAD_REQUEST)

        relogin = APIClient().post(LOGIN, credentials, format="json")
        self.assertEqual(relogin.status_code, status.HTTP_200_OK)
        self.assertEqual(
            user_client.get("/api/leads/").status_code, status.HTTP_200_OK
        )

    def test_onboarding_company_is_not_blocked(self):
        company = make_company("Onboarding", status=DjangoCompanyModel.Status.ONBOARDING)
        user = make_user(company, role=User.Role.SUPERADMIN)

        response = token_client(user).get("/api/leads/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_suspending_one_company_does_not_affect_another(self):
        victim = make_company("Victim")
        bystander = make_company("Bystander")
        bystander_user = make_user(bystander, role=User.Role.SUPERADMIN)
        self.client.post(
            f"{BASE}{victim.id}/suspend/", {"reason": "test"}, format="json"
        )

        response = token_client(bystander_user).get("/api/leads/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PlatformCompaniesPermissionTests(APITestCase):

    def setUp(self):
        self.company = make_company("Tenant")
        self.target = make_company("Target")

    def endpoints(self):
        url = f"{BASE}{self.target.id}/"
        return (
            ("get", BASE, None),
            ("post", BASE, valid_payload()),
            ("get", url, None),
            ("patch", url, {"name": "Hacked"}),
            ("post", f"{url}suspend/", {"reason": "nope"}),
            ("post", f"{url}activate/", None),
        )

    def assert_denied(self, client, expected):
        for method, url, body in self.endpoints():
            with self.subTest(method=method, url=url):
                response = getattr(client, method)(url, body, format="json")
                self.assertIn(response.status_code, expected)

    def test_company_roles_are_forbidden(self):
        for role in (User.Role.SUPERADMIN, User.Role.ADMIN):
            with self.subTest(role=role):
                user = make_user(self.company, role=role)
                self.assert_denied(
                    authenticated_client(user), {status.HTTP_403_FORBIDDEN}
                )

        self.target.refresh_from_db()
        self.assertEqual(self.target.status, DjangoCompanyModel.Status.ACTIVE)
        self.assertEqual(self.target.name, "Target")
        self.assertFalse(User.objects.filter(email="alice@acme.example.com").exists())

    def test_anonymous_is_rejected(self):
        self.assert_denied(
            APIClient(),
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )
