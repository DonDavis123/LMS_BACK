from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

PICKLISTS = "/api/picklists/accounts/"
FIELDS = ["account_type", "industry", "rating", "ownership"]


def make_account(company, owner, name, **extra):
    now = timezone.now()
    return DjangoAccountModel.objects.create(
        company=company,
        account_owner=owner,
        account_name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


class AccountDropdownUpdateTests(APITestCase):
    def setUp(self):
        self.company_a = make_company("Account Pick A", "apick-a")
        self.company_b = make_company("Account Pick B", "apick-b")
        self.super_a = make_user(self.company_a, User.Role.SUPERADMIN, "apick-super-a@example.com")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "apick-admin-a@example.com")
        self.super_b = make_user(self.company_b, User.Role.SUPERADMIN, "apick-super-b@example.com")
        self.sa = authenticated_client(self.super_a)
        self.adm = authenticated_client(self.admin_a)
        self.sb = authenticated_client(self.super_b)

    def update_url(self, account):
        return f"/api/accounts/{account.id}/update"

    def put(self, client, account, **extra):
        return client.put(
            self.update_url(account),
            {"account_name": account.account_name, **extra},
            format="json",
        )

    def option_id(self, client, field, value):
        response = client.get(f"{PICKLISTS}{field}/", {"include_inactive": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return next(o["id"] for o in response.data["options"] if o["value"] == value)

    def test_company_gets_default_account_dropdowns(self):
        response = self.adm.get(PICKLISTS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([f["field"] for f in response.data["fields"]], FIELDS)
        types = [o["value"] for o in self.adm.get(f"{PICKLISTS}account_type/").data["options"]]
        self.assertEqual(types[0], "None")
        self.assertIn("Customer", types)

    def test_accounts_and_leads_options_are_independent(self):
        self.sa.post(f"{PICKLISTS}industry/create/", {"value": "Aerospace"}, format="json")
        leads = self.sa.get("/api/picklists/leads/industry/")
        self.assertNotIn("Aerospace", [o["value"] for o in leads.data["options"]])

    def test_update_accepts_active_options_and_normalises_case(self):
        account = make_account(self.company_a, self.super_a, "Acme")
        response = self.put(
            self.sa, account,
            account_type="customer", industry="isv", rating="active", ownership="privately held",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        account.refresh_from_db()
        self.assertEqual(
            (account.account_type, account.industry, account.rating, account.ownership),
            ("Customer", "ISV", "Active", "Privately Held"),
        )

    def test_update_accepts_company_custom_option(self):
        self.sa.post(f"{PICKLISTS}ownership/create/", {"value": "Cooperative"}, format="json")
        account = make_account(self.company_a, self.super_a, "Acme")
        response = self.put(self.sa, account, ownership="Cooperative")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        account.refresh_from_db()
        self.assertEqual(account.ownership, "Cooperative")

    def test_update_rejects_unknown_value_and_changes_nothing(self):
        account = make_account(self.company_a, self.super_a, "Acme", account_type="Partner")
        response = self.put(self.sa, account, account_type="Partner", rating="Platinum")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        self.assertIsNone(account.rating)

    def test_other_company_option_is_not_valid(self):
        self.sb.post(f"{PICKLISTS}account_type/create/", {"value": "Only B"}, format="json")
        account = make_account(self.company_a, self.super_a, "Acme")
        response = self.put(self.sa, account, account_type="Only B")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hidden_option_rejected_but_kept_when_unchanged(self):
        account = make_account(self.company_a, self.super_a, "Acme", account_type="Press")
        option_id = self.option_id(self.sa, "account_type", "Press")
        hide = self.sa.patch(f"/api/picklists/options/{option_id}/update/", {"is_active": False}, format="json")
        self.assertEqual(hide.status_code, status.HTTP_200_OK, hide.content)

        keep = self.put(self.sa, account, account_type="Press", phone="12345")
        self.assertEqual(keep.status_code, status.HTTP_200_OK, keep.content)

        other = make_account(self.company_a, self.super_a, "Beta")
        rejected = self.put(self.sa, other, account_type="Press")
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_or_missing_dropdown_becomes_none_option(self):
        account = make_account(
            self.company_a, self.super_a, "Acme", account_type="Partner", rating="Active"
        )
        response = self.put(self.sa, account, account_type="")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        account.refresh_from_db()
        self.assertEqual(account.account_type, "None")
        self.assertEqual(account.rating, "None")
        self.assertEqual(account.ownership, "None")

    def test_renaming_option_moves_accounts_of_that_company_only(self):
        mine = make_account(self.company_a, self.super_a, "Acme", account_type="Vendor")
        theirs = make_account(self.company_b, self.super_b, "Zed", account_type="Vendor")
        option_id = self.option_id(self.sa, "account_type", "Vendor")
        response = self.sa.patch(
            f"/api/picklists/options/{option_id}/update/", {"value": "Supplier Vendor"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.account_type, "Supplier Vendor")
        self.assertEqual(theirs.account_type, "Vendor")

    def test_deleting_option_in_use_needs_replacement(self):
        make_account(self.company_a, self.super_a, "Acme", ownership="Public")
        option_id = self.option_id(self.sa, "ownership", "Public")
        response = self.sa.delete(f"/api/picklists/options/{option_id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        self.assertEqual(response.data["usage_count"], 1)

    def test_admin_cannot_edit_options(self):
        response = self.adm.post(f"{PICKLISTS}rating/create/", {"value": "Nope"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
