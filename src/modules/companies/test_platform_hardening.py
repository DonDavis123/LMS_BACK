from unittest.mock import patch

from rest_framework.test import APITestCase

from src.modules.companies.infrastructure.persistence.platform_audit_log_model import (
    PlatformAuditLogModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User


class PlatformHardeningTests(APITestCase):

    def setUp(self):
        self.platform = make_user(None, role=User.Role.PLATFORM_SUPERADMIN)
        self.client = authenticated_client(self.platform)
        self.company = make_company(name="Acme")
        self.url = f"/api/platform/companies/{self.company.id}/"

    def _updates(self):
        return PlatformAuditLogModel.objects.filter(
            company_id=self.company.id, action="COMPANY_UPDATED"
        )

    def test_unchanged_update_writes_no_audit_entry(self):
        response = self.client.patch(self.url, {"name": "Acme"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._updates().count(), 0)

    def test_only_really_changed_fields_are_audited(self):
        response = self.client.patch(
            self.url, {"name": "Acme", "website": "https://a.example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["website"], "https://a.example.com")
        self.assertEqual(self._updates().get().metadata, {"changed_fields": ["website"]})

    def test_rename_persists(self):
        self.client.patch(self.url, {"name": "  Renamed  "}, format="json")
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Renamed")

    def test_unknown_audit_action_does_not_break_the_list(self):
        PlatformAuditLogModel.objects.create(
            action="LEGACY_THING",
            actor_id=self.platform.id,
            actor_email=self.platform.email,
            company_id=self.company.id,
        )
        response = self.client.get("/api/platform/audit-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["action"], "LEGACY_THING")


class JsonServerErrorTests(APITestCase):

    def test_unexpected_error_returns_json_500(self):
        platform = make_user(None, role=User.Role.PLATFORM_SUPERADMIN)
        client = authenticated_client(platform)
        client.raise_request_exception = False
        with patch(
            "src.modules.companies.presentation.api.views.platform_overview."
            "get_platform_overview_use_case",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/platform/overview/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn("boom", response.content.decode())
