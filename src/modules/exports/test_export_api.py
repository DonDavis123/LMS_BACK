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
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
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
        self.account = None
        for company, owner, name in (
            (self.company, self.admin, "Acme Corp"),
            (self.other_company, self.other_admin, "Foreign Corp"),
        ):
            account = DjangoAccountModel.objects.create(
                company=company, account_owner=owner, account_name=name,
                created_by=owner, created_at=now, modified_by=owner, updated_at=now,
                **(
                    {
                        "account_type": "Customer",
                        "industry": "Software",
                        "billing_city": "Kochi",
                        "billing_country": "India",
                        "employees": 120,
                        "annual_revenue": 2500000,
                    }
                    if company == self.company
                    else {}
                ),
            )
            if company == self.company:
                self.account = account
        DjangoAccountModel.objects.create(
            company=self.company, account_owner=self.admin, account_name="Gone Corp",
            is_deleted=True, created_by=self.admin, created_at=now,
            modified_by=self.admin, updated_at=now,
        )

        def contact(company, owner, name, account=None, **extra):
            return DjangoContactModel.objects.create(
                company=company, account=account, contact_owner=owner, name=name,
                created_by=owner, created_at=now, modified_by=owner, updated_at=now,
                **extra,
            )

        contact(
            self.company, self.admin, "Meera Nair", account=self.account,
            email="meera@acme.test", title="Head of Sales", department="Sales",
            mailing_city="Kochi", email_opt_out=True,
        )
        contact(self.company, self.admin, "Zed Contact", email="zed@acme.test")
        contact(self.company, self.admin, "=HYPERLINK(\"x\")")
        contact(self.company, self.admin, "Gone Contact", is_deleted=True)
        contact(self.other_company, self.other_admin, "Foreign Contact")

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
        self.assertEqual(by_filter.status_code, status.HTTP_200_OK)
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

        self.assertTrue(lines[0].startswith("Account Name,Account Number,Account Type"))
        self.assertEqual(len(lines), 2)  # header + Acme Corp only
        text = "\n".join(lines)
        self.assertIn("Acme Corp", text)
        self.assertNotIn("Foreign Corp", text)
        self.assertNotIn("Gone Corp", text)

    def test_accounts_export_has_the_full_account_details(self):
        response = self.client.get("/api/exports/accounts/", {"format": "xlsx"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sheet = load_workbook(io.BytesIO(_download(response))).active
        headers = [cell.value for cell in sheet[1]]
        row = dict(zip(headers, [cell.value for cell in sheet[2]]))
        self.assertEqual(row["Account Name"], "Acme Corp")
        self.assertEqual(row["Account Type"], "Customer")
        self.assertEqual(row["Industry"], "Software")
        self.assertEqual(row["Billing City"], "Kochi")
        self.assertEqual(row["Billing Country"], "India")
        self.assertEqual(row["Employees"], 120)
        self.assertEqual(row["Annual Revenue"], 2500000)
        self.assertEqual(row["Owner"], "Admin One")
        self.assertRegex(row["Created At"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_accounts_export_follows_search_and_filters(self):
        none = self._csv_lines(self.client.get("/api/exports/accounts/", {"search": "zzz"}))
        self.assertEqual(len(none), 1)

        filters = json.dumps(
            [{"field": "billing_city", "operator": "equals", "value": "Kochi"}]
        )
        response = self.client.get("/api/exports/accounts/", {"filters": filters})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self._csv_lines(response)), 2)

    def test_contacts_export_is_scoped_to_the_company(self):
        response = self.client.get("/api/exports/contacts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contacts-", response["Content-Disposition"])
        lines = self._csv_lines(response)
        self.assertTrue(lines[0].startswith("Name,Title,Department,Email"))
        text = "\n".join(lines)
        self.assertIn("Meera Nair", text)
        self.assertIn("Zed Contact", text)
        self.assertNotIn("Gone Contact", text)
        self.assertNotIn("Foreign Contact", text)
        self.assertEqual(len(lines), 4)  # header + 3 contacts

    def test_contacts_export_has_the_full_contact_details(self):
        response = self.client.get(
            "/api/exports/contacts/", {"format": "xlsx", "search": "meera"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sheet = load_workbook(io.BytesIO(_download(response))).active
        self.assertEqual(sheet.max_row, 2)
        headers = [cell.value for cell in sheet[1]]
        row = dict(zip(headers, [cell.value for cell in sheet[2]]))
        self.assertEqual(row["Name"], "Meera Nair")
        self.assertEqual(row["Title"], "Head of Sales")
        self.assertEqual(row["Department"], "Sales")
        self.assertEqual(row["Email"], "meera@acme.test")
        self.assertEqual(row["Account"], "Acme Corp")
        self.assertEqual(row["Owner"], "Admin One")
        self.assertEqual(row["Mailing City"], "Kochi")
        self.assertEqual(row["Email Opt Out"], "Yes")

    def test_contacts_export_keeps_the_list_sort_order(self):
        response = self.client.get(
            "/api/exports/contacts/", {"sort_by": "name", "sort_direction": "desc"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [line.split(",")[0] for line in self._csv_lines(response)[1:]]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_contacts_export_neutralises_spreadsheet_formulas(self):
        text = "\n".join(self._csv_lines(self.client.get("/api/exports/contacts/")))

        self.assertIn("'=HYPERLINK", text)

    def test_contacts_and_accounts_exports_are_open_to_company_users(self):
        executive = authenticated_client(self.executive)
        for entity in ("contacts", "accounts"):
            response = executive.get(f"/api/exports/{entity}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK, entity)

    def test_exports_need_a_signed_in_user(self):
        from rest_framework.test import APIClient

        for entity in ("contacts", "accounts"):
            response = APIClient().get(f"/api/exports/{entity}/")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, entity)

    def test_other_entities_answer_with_a_file(self):
        for entity in ("tasks", "calls", "meetings"):
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
