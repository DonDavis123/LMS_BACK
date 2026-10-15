from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.users.infrastructure.persistence.models import User

LOGIN = "/api/auth/login/"


def users_url(company, suffix=""):
    return f"/api/platform/companies/{company.id}/users/{suffix}"


def login(email, password):
    return APIClient().post(
        LOGIN, {"email": email, "password": password}, format="json"
    )


class PlatformCompanyUsersApiTests(APITestCase):

    def setUp(self):
        self.platform_admin = make_user(
            None, role=User.Role.PLATFORM_SUPERADMIN, email="platform@example.com"
        )
        self.client = authenticated_client(self.platform_admin)
        self.company = make_company("Acme")
        self.owner = make_user(
            self.company, role=User.Role.SUPERADMIN, email="owner@acme.example.com"
        )
        self.member = make_user(
            self.company, role=User.Role.ADMIN, email="member@acme.example.com"
        )

    # --- list -------------------------------------------------------------

    def test_list_users_with_filters_and_pagination(self):
        make_user(make_company("Other"), email="stranger@example.com")
        self.member.is_active = False
        self.member.save()

        response = self.client.get(users_url(self.company))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {u["email"] for u in response.data["results"]},
            {"owner@acme.example.com", "member@acme.example.com"},
        )
        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertEqual(
            set(response.data["results"][0]),
            {"id", "name", "email", "role", "is_active", "created_at"},
        )

        by_search = self.client.get(users_url(self.company), {"search": "owner"})
        self.assertEqual(len(by_search.data["results"]), 1)

        by_role = self.client.get(users_url(self.company), {"role": "ADMIN"})
        self.assertEqual(
            [u["email"] for u in by_role.data["results"]], ["member@acme.example.com"]
        )

        inactive = self.client.get(users_url(self.company), {"is_active": "false"})
        self.assertEqual(
            [u["email"] for u in inactive.data["results"]], ["member@acme.example.com"]
        )

        ordered = self.client.get(
            users_url(self.company), {"sort_by": "email", "sort_direction": "desc"}
        )
        self.assertEqual(
            [u["email"] for u in ordered.data["results"]],
            ["owner@acme.example.com", "member@acme.example.com"],
        )

        paged = self.client.get(users_url(self.company), {"page_size": 1, "page": 2})
        self.assertEqual(len(paged.data["results"]), 1)
        self.assertEqual(paged.data["pagination"]["total_pages"], 2)

    def test_list_rejects_bad_query(self):
        for params in ({"role": "NOPE"}, {"is_active": "maybe"}, {"page": "0"}):
            with self.subTest(params=params):
                response = self.client.get(users_url(self.company), params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_company_is_404(self):
        ghost = DjangoCompanyModel(id="00000000-0000-0000-0000-000000000000")
        for method, suffix, body in (
            ("get", "", None),
            ("post", "", {"name": "N", "email": "n@x.com", "password": "password123", "role": "ADMIN"}),
        ):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    users_url(ghost, suffix), body, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.data, {"detail": "Company not found."})

    def test_suspended_company_can_still_be_managed(self):
        self.company.status = DjangoCompanyModel.Status.SUSPENDED
        self.company.save()

        self.assertEqual(
            self.client.get(users_url(self.company)).status_code, status.HTTP_200_OK
        )
        response = self.client.post(
            users_url(self.company, f"{self.member.id}/reset-password/"),
            {"new_password": "brand-new-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # --- create -----------------------------------------------------------

    def test_create_user(self):
        response = self.client.post(
            users_url(self.company),
            {
                "name": "New Admin",
                "email": "New@Acme.example.com",
                "password": "good-password",
                "role": "ADMIN",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="new@acme.example.com")
        self.assertEqual(created.company_id, self.company.id)
        self.assertEqual(created.role, User.Role.ADMIN)
        self.assertNotIn("password", response.data)
        self.assertEqual(login("new@acme.example.com", "good-password").status_code, 200)

    def test_create_rejects_unmanageable_role_and_weak_password(self):
        for override in (
            {"role": "PLATFORM_SUPERADMIN"},
            {"role": "SALES_MANAGER"},
            {"password": "short"},
        ):
            with self.subTest(override=override):
                body = {
                    "name": "X",
                    "email": "x@acme.example.com",
                    "password": "good-password",
                    "role": "ADMIN",
                    **override,
                }
                response = self.client.post(users_url(self.company), body, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="x@acme.example.com").exists())

    def test_duplicate_email_across_companies_is_rejected(self):
        other = make_company("Other")
        make_user(other, email="taken@example.com")

        for email in ("taken@example.com", "TAKEN@example.com"):
            with self.subTest(email=email):
                response = self.client.post(
                    users_url(self.company),
                    {
                        "name": "Dup",
                        "email": email,
                        "password": "good-password",
                        "role": "ADMIN",
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    response.data["detail"], "User with this email already exists."
                )

    # --- reset password ---------------------------------------------------

    def test_reset_password_changes_password_and_revokes_sessions(self):
        before = login("member@acme.example.com", "password123")
        self.assertEqual(before.status_code, status.HTTP_200_OK)

        response = self.client.post(
            users_url(self.company, f"{self.member.id}/reset-password/"),
            {"new_password": "brand-new-pass"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            login("member@acme.example.com", "password123").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            login("member@acme.example.com", "brand-new-pass").status_code,
            status.HTTP_200_OK,
        )

    def test_reset_password_validates(self):
        response = self.client.post(
            users_url(self.company, f"{self.member.id}/reset-password/"),
            {"new_password": "short"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- block / unblock --------------------------------------------------

    def test_block_and_unblock(self):
        block = self.client.post(users_url(self.company, f"{self.member.id}/block/"))
        self.assertEqual(block.status_code, status.HTTP_200_OK)
        self.assertFalse(block.data["is_active"])
        self.assertEqual(
            login("member@acme.example.com", "password123").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        unblock = self.client.post(
            users_url(self.company, f"{self.member.id}/unblock/")
        )
        self.assertEqual(unblock.status_code, status.HTTP_200_OK)
        self.assertTrue(unblock.data["is_active"])
        self.assertEqual(
            login("member@acme.example.com", "password123").status_code,
            status.HTTP_200_OK,
        )

    def test_blocking_revokes_existing_refresh_tokens(self):
        from django.conf import settings

        first = login("member@acme.example.com", "password123")
        refresh = first.cookies[settings.REFRESH_COOKIE_NAME].value
        self.client.post(users_url(self.company, f"{self.member.id}/block/"))
        self.client.post(users_url(self.company, f"{self.member.id}/unblock/"))

        client = APIClient()
        client.cookies[settings.REFRESH_COOKIE_NAME] = refresh
        self.assertEqual(
            client.post("/api/auth/refresh/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # --- targeting rules --------------------------------------------------

    def test_cross_company_target_is_404(self):
        other = make_company("Other")
        outsider = make_user(other, email="outsider@example.com")

        for suffix, body in (
            ("reset-password/", {"new_password": "brand-new-pass"}),
            ("block/", None),
            ("unblock/", None),
        ):
            with self.subTest(suffix=suffix):
                response = self.client.post(
                    users_url(self.company, f"{outsider.id}/{suffix}"),
                    body,
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.data, {"detail": "User not found."})

        outsider.refresh_from_db()
        self.assertTrue(outsider.is_active)
        self.assertTrue(outsider.check_password("password123"))

    def test_platform_admin_can_never_be_targeted(self):
        other_admin = make_user(
            None, role=User.Role.PLATFORM_SUPERADMIN, email="other-platform@example.com"
        )

        for target in (other_admin, self.platform_admin):
            for suffix, body in (
                ("reset-password/", {"new_password": "brand-new-pass"}),
                ("block/", None),
                ("unblock/", None),
            ):
                with self.subTest(target=target.email, suffix=suffix):
                    response = self.client.post(
                        users_url(self.company, f"{target.id}/{suffix}"),
                        body,
                        format="json",
                    )
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        other_admin.refresh_from_db()
        self.assertTrue(other_admin.is_active)
        self.assertTrue(other_admin.check_password("password123"))


class PlatformCompanyUsersPermissionTests(APITestCase):

    def setUp(self):
        self.company = make_company("Acme")
        self.target = make_user(self.company, role=User.Role.ADMIN, email="t@acme.example.com")

    def endpoints(self):
        return (
            ("get", users_url(self.company), None),
            (
                "post",
                users_url(self.company),
                {"name": "N", "email": "n@x.com", "password": "password123", "role": "ADMIN"},
            ),
            (
                "post",
                users_url(self.company, f"{self.target.id}/reset-password/"),
                {"new_password": "hacked-pass-1"},
            ),
            ("post", users_url(self.company, f"{self.target.id}/block/"), None),
            ("post", users_url(self.company, f"{self.target.id}/unblock/"), None),
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
                self.assert_denied(authenticated_client(user), {status.HTTP_403_FORBIDDEN})

        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(self.target.check_password("password123"))
        self.assertFalse(User.objects.filter(email="n@x.com").exists())

    def test_anonymous_is_rejected(self):
        self.assert_denied(
            APIClient(), {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
        )
