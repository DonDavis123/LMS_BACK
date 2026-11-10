from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_audit_log_model import (
    DjangoUserAuditLogModel,
)

SELF_URL = "/api/users/me/google-email/"
ME_URL = "/api/users/me/"


class SelfGoogleEmailTests(APITestCase):

    def setUp(self):
        self.company = make_company("Acme")
        self.user = make_user(
            self.company,
            role=User.Role.SALES_EXECUTIVE,
            email="rep@acme.com",
        )
        self.client = authenticated_client(self.user)

    def patch(self, value):
        return self.client.patch(
            SELF_URL, {"google_email": value}, format="json"
        )

    def test_set_google_email(self):
        response = self.patch("rep@gmail.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["google_email"], "rep@gmail.com")
        self.assertEqual(response.data["mail_account_email"], "rep@gmail.com")
        self.assertEqual(response.data["email"], "rep@acme.com")
        self.assertEqual(response.data["company"]["name"], "Acme")
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_email, "rep@gmail.com")

    def test_response_matches_current_user_payload(self):
        response = self.patch("rep@gmail.com")

        self.assertEqual(
            dict(response.data),
            dict(self.client.get(ME_URL).data),
        )

    def test_clear_google_email(self):
        self.patch("rep@gmail.com")

        response = self.patch(None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["google_email"])
        self.assertEqual(response.data["mail_account_email"], "rep@acme.com")
        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_email)

    def test_blank_string_clears_google_email(self):
        self.patch("rep@gmail.com")

        response = self.patch("   ")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["google_email"])

    def test_google_email_is_normalised(self):
        response = self.patch("  Rep.Name@GMail.COM  ")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["google_email"], "rep.name@gmail.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_email, "rep.name@gmail.com")

    def test_workspace_domain_is_allowed(self):
        response = self.patch("rep@some-company.io")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_email_returns_400_detail(self):
        for value in ("not-an-email", "a@b", "two@@x.com", "a b@x.com"):
            with self.subTest(value=value):
                response = self.patch(value)

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn("detail", response.data)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.google_email)
        self.assertFalse(DjangoUserAuditLogModel.objects.exists())

    def test_missing_field_returns_400(self):
        response = self.client.patch(SELF_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mail_account_email_falls_back_to_login_email(self):
        response = self.client.get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["google_email"])
        self.assertEqual(response.data["mail_account_email"], "rep@acme.com")

    def test_google_email_is_not_unique(self):
        other = make_user(self.company, email="other@acme.com")
        authenticated_client(other).patch(
            SELF_URL, {"google_email": "shared@gmail.com"}, format="json"
        )

        response = self.patch("shared@gmail.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_writes_audit_log(self):
        self.patch("rep@gmail.com")
        self.patch("Rep2@gmail.com")

        logs = DjangoUserAuditLogModel.objects.filter(
            action="USER_UPDATED",
        ).order_by("created_at")
        self.assertEqual(logs.count(), 2)
        first, second = list(logs)
        self.assertEqual(first.actor_id, self.user.id)
        self.assertEqual(first.target_user_id, self.user.id)
        self.assertEqual(first.company_id, self.company.id)
        self.assertEqual(
            first.metadata["changes"]["google_email"],
            {"from": None, "to": "rep@gmail.com"},
        )
        self.assertEqual(
            second.metadata["changes"]["google_email"],
            {"from": "rep@gmail.com", "to": "rep2@gmail.com"},
        )

    def test_unchanged_value_writes_no_audit_log(self):
        self.patch("rep@gmail.com")
        self.patch("REP@gmail.com")

        self.assertEqual(DjangoUserAuditLogModel.objects.count(), 1)

    def test_unauthenticated_gets_401(self):
        response = self.client_class().patch(
            SELF_URL, {"google_email": "a@gmail.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_superadmin_cannot_use_company_endpoint(self):
        # Like every tenant endpoint: no company, no company-level audit
        # trail. GET /users/me/ still works for them and reports no google_email.
        platform_admin = make_user(None, role=User.Role.PLATFORM_SUPERADMIN)
        client = authenticated_client(platform_admin)

        response = client.patch(
            SELF_URL, {"google_email": "a@gmail.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        me = client.get(ME_URL)
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertIsNone(me.data["google_email"])
        self.assertEqual(me.data["mail_account_email"], platform_admin.email)
        platform_admin.refresh_from_db()
        self.assertIsNone(platform_admin.google_email)

    def test_cannot_change_another_users_value(self):
        other = make_user(self.company, email="other@acme.com")
        other.google_email = "other@gmail.com"
        other.save(update_fields=["google_email"])

        response = self.client.patch(
            SELF_URL,
            {"google_email": "hijack@gmail.com", "user_id": str(other.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        other.refresh_from_db()
        self.assertEqual(other.google_email, "other@gmail.com")

        response = self.patch("mine@gmail.com")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(other.google_email, "other@gmail.com")
        self.assertEqual(self.user.google_email, "mine@gmail.com")

    def test_other_company_user_is_untouched(self):
        other_company = make_company("Other")
        outsider = make_user(other_company, email="out@other.com")

        self.patch("rep@gmail.com")

        outsider.refresh_from_db()
        self.assertIsNone(outsider.google_email)


class AdminGoogleEmailTests(APITestCase):

    def setUp(self):
        self.company = make_company("Acme")
        self.superadmin = make_user(
            self.company, role=User.Role.SUPERADMIN, email="boss@acme.com"
        )
        self.target = make_user(
            self.company, role=User.Role.ADMIN, email="target@acme.com"
        )
        self.client = authenticated_client(self.superadmin)
        self.url = f"/api/users/{self.target.id}/"

    def test_admin_sets_google_email(self):
        response = self.client.patch(
            self.url, {"google_email": " Target@GMail.com "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["google_email"], "target@gmail.com")
        self.assertEqual(response.data["mail_account_email"], "target@gmail.com")
        log = DjangoUserAuditLogModel.objects.get(action="USER_UPDATED")
        self.assertEqual(log.actor_id, self.superadmin.id)
        self.assertEqual(log.target_user_id, self.target.id)
        self.assertEqual(
            log.metadata["changes"],
            {"google_email": {"from": None, "to": "target@gmail.com"}},
        )

    def test_omitted_leaves_value_unchanged(self):
        self.client.patch(
            self.url, {"google_email": "target@gmail.com"}, format="json"
        )

        response = self.client.patch(
            self.url, {"name": "Renamed"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["google_email"], "target@gmail.com")

    def test_null_clears_value(self):
        self.client.patch(
            self.url, {"google_email": "target@gmail.com"}, format="json"
        )

        response = self.client.patch(
            self.url, {"google_email": None}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["google_email"])
        self.assertEqual(response.data["mail_account_email"], "target@acme.com")
        self.assertEqual(
            DjangoUserAuditLogModel.objects.filter(action="USER_UPDATED").count(),
            2,
        )

    def test_invalid_google_email_rejected(self):
        response = self.client.patch(
            self.url, {"google_email": "nope"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("google_email", response.data)

    def test_non_superadmin_cannot_update(self):
        client = authenticated_client(
            make_user(self.company, role=User.Role.ADMIN)
        )

        response = client.patch(
            self.url, {"google_email": "x@gmail.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_company_user_cannot_be_updated(self):
        outsider = make_user(make_company("Other"), email="out@other.com")

        response = self.client.patch(
            f"/api/users/{outsider.id}/",
            {"google_email": "x@gmail.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        outsider.refresh_from_db()
        self.assertIsNone(outsider.google_email)

    def test_detail_and_list_include_new_fields(self):
        self.client.patch(
            self.url, {"google_email": "target@gmail.com"}, format="json"
        )

        detail = self.client.get(self.url)
        listing = self.client.get("/api/users/")

        self.assertEqual(detail.data["google_email"], "target@gmail.com")
        self.assertEqual(detail.data["mail_account_email"], "target@gmail.com")
        rows = {row["email"]: row for row in listing.data["results"]}
        self.assertEqual(
            rows["target@acme.com"]["google_email"], "target@gmail.com"
        )
        self.assertEqual(
            rows["target@acme.com"]["mail_account_email"], "target@gmail.com"
        )
        self.assertIsNone(rows["boss@acme.com"]["google_email"])
        self.assertEqual(
            rows["boss@acme.com"]["mail_account_email"], "boss@acme.com"
        )
