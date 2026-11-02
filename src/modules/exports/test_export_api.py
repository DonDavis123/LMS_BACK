import io
import json
from datetime import timedelta

from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User


def _download(response) -> bytes:
    return b"".join(response.streaming_content)


class ExportApiTests(APITestCase):
    """HTTP -> view -> export use case -> list use case -> repository -> file."""

    def setUp(self):
        self.company = make_company("Export Co")
        self.other_company = make_company("Other Co")
        self.admin = make_user(self.company, User.Role.ADMIN, name="Admin One")
        self.other_admin = make_user(self.other_company, User.Role.ADMIN)
        self.executive = make_user(self.company, User.Role.SALES_EXECUTIVE)
        self.client = authenticated_client(self.admin)

        def lead(company, owner, name, **extra):
            return DjangoLeadModel.objects.create(
                company=company, owner=owner, name=name, **extra
            )

        lead(self.company, self.admin, "Asha Rao", company_name="Acme", lead_status="New")
        lead(self.company, self.admin, "Ben Cole", company_name="Beta", lead_status="Contacted")
        lead(self.company, self.admin, "Gone Lead", is_deleted=True)
        lead(self.company, self.admin, "Converted Lead", is_converted=True)
        lead(self.other_company, self.other_admin, "Foreign Lead")

        now = timezone.now()
        for company, owner, name in (
            (self.company, self.admin, "Acme Corp"),
            (self.other_company, self.other_admin, "Foreign Corp"),
        ):
            DjangoAccountModel.objects.create(
                company=company, account_owner=owner, account_name=name,
                created_by=owner, created_at=now, modified_by=owner, updated_at=now,
            )

    def _csv_lines(self, response):
        return _download(response).decode("utf-8-sig").strip().split("\r\n")

    def test_leads_csv_has_only_listed_leads_of_the_callers_company(self):
        response = self.client.get("/api/exports/leads/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("leads-", response["Content-Disposition"])
        lines = self._csv_lines(response)
        self.assertTrue(lines[0].startswith("Name,Company,Email"))
        text = "\n".join(lines)
        self.assertIn("Asha Rao", text)
        self.assertIn("Ben Cole", text)
        self.assertNotIn("Gone Lead", text)
        self.assertNotIn("Converted Lead", text)
        self.assertNotIn("Foreign Lead", text)
        self.assertEqual(len(lines), 3)

    def test_search_and_filters_narrow_the_export(self):
        by_search = self._csv_lines(self.client.get("/api/exports/leads/", {"search": "asha"}))
        self.assertEqual(len(by_search), 2)

        filters = json.dumps(
            [{"field": "lead_status", "operator": "equals", "value": "Contacted"}]
        )
        by_filter = self.client.get("/api/exports/leads/", {"filters": filters})
        self.assertEqual(by_filter.status_code, status.HTTP_200_OK, by_filter.content)
        lines = self._csv_lines(by_filter)
        self.assertEqual(len(lines), 2)
        self.assertIn("Ben Cole", lines[1])

    def test_xlsx_download(self):
        response = self.client.get("/api/exports/leads/", {"format": "xlsx"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("spreadsheetml", response["Content-Type"])
        self.assertIn(".xlsx", response["Content-Disposition"])
        sheet = load_workbook(io.BytesIO(_download(response))).active
        self.assertEqual(sheet.max_row, 3)
        self.assertEqual(sheet["A1"].value, "Name")

    def test_accounts_export_is_scoped_to_the_company(self):
        lines = self._csv_lines(self.client.get("/api/exports/accounts/"))

        self.assertEqual(lines[0], "Account Name,Phone,Website,Owner")
        self.assertEqual(len(lines), 2)
        self.assertIn("Acme Corp", lines[1])

    def test_other_entities_answer_with_a_file(self):
        for entity in ("contacts", "tasks", "calls", "meetings"):
            response = self.client.get(f"/api/exports/{entity}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK, entity)
            self.assertEqual(len(self._csv_lines(response)), 1, entity)  # header only

    def test_meetings_do_not_accept_filters(self):
        filters = json.dumps([{"field": "title", "operator": "equals", "value": "x"}])
        response = self.client.get("/api/exports/meetings/", {"filters": filters})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bad_format_and_bad_filters_are_400(self):
        self.assertEqual(
            self.client.get("/api/exports/leads/", {"format": "pdf"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get("/api/exports/leads/", {"filters": "not json"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unknown_export_is_404(self):
        self.assertEqual(
            self.client.get("/api/exports/unicorns/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_sales_executive_cannot_export_leads_but_can_export_accounts(self):
        client = authenticated_client(self.executive)

        self.assertEqual(
            client.get("/api/exports/leads/").status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            client.get("/api/exports/accounts/").status_code, status.HTTP_200_OK
        )

    def test_anonymous_and_platform_users_are_refused(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get("/api/exports/leads/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN)
        self.assertEqual(
            authenticated_client(platform).get("/api/exports/leads/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
