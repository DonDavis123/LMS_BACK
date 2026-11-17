import uuid

from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.deals.deal_factories import make_account, make_contact, make_deal
from src.modules.deals.infrastructure.persistence.models import DjangoDealModel
from src.modules.deals.infrastructure.persistence.django_deal_repository import (
    DjangoDealRepository,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
from src.modules.users.infrastructure.persistence.models import User

URL = "/api/deals/"


class DealTenantIsolationTests(APITestCase):
    """Company A owns a deal; company B must not be able to touch it."""

    def setUp(self):
        self.company_a = make_company("Company A", "company-a")
        self.company_b = make_company("Company B", "company-b")

        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "admin-a@example.com")
        self.super_a = make_user(self.company_a, User.Role.SUPERADMIN, "super-a@example.com")
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "admin-b@example.com")
        self.super_b = make_user(self.company_b, User.Role.SUPERADMIN, "super-b@example.com")

        self.client_a = authenticated_client(self.super_a)
        self.client_b = authenticated_client(self.super_b)

        self.account_a = make_account(self.company_a, self.admin_a, "Acme A")
        self.contact_a = make_contact(self.company_a, self.admin_a, "Jane A", account=self.account_a)
        self.account_b = make_account(self.company_b, self.admin_b, "Acme B")
        self.contact_b = make_contact(self.company_b, self.admin_b, "Jane B", account=self.account_b)

        self.deal_a = make_deal(
            self.company_a, self.admin_a, account=self.account_a, name="A's deal"
        )
        self.deal_b = make_deal(
            self.company_b, self.admin_b, account=self.account_b, name="B's deal"
        )

    def missing(self):
        return uuid.uuid4()

    def test_list_only_shows_own_company(self):
        response = self.client_b.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["name"] for row in response.data["results"]], ["B's deal"])
        self.assertEqual(response.data["pagination"]["total"], 1)

    def test_filters_and_search_cannot_reach_other_companies(self):
        import json

        by_filter = self.client_b.get(
            URL,
            {"filters": json.dumps([
                {"field": "name", "operator": "equals", "value": "A's deal"}
            ])},
        )
        by_search = self.client_b.get(URL, {"search": "A's"})
        by_owner = self.client_b.get(
            URL,
            {"filters": json.dumps([
                {"field": "owner", "operator": "equals", "value": str(self.admin_a.id)}
            ])},
        )

        for response in (by_filter, by_search, by_owner):
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["results"], [])

    def test_read_foreign_deal_is_like_a_missing_one(self):
        foreign = self.client_b.get(f"{URL}{self.deal_a.id}/")
        missing = self.client_b.get(f"{URL}{self.missing()}/")

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)

    def test_update_foreign_deal_is_like_a_missing_one(self):
        foreign = self.client_b.patch(f"{URL}{self.deal_a.id}/", {"name": "hacked"}, format="json")
        missing = self.client_b.patch(f"{URL}{self.missing()}/", {"name": "hacked"}, format="json")

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.name, "A's deal")

    def test_move_foreign_deal_is_like_a_missing_one(self):
        foreign = self.client_b.post(f"{URL}{self.deal_a.id}/move/", {"stage": "Won"}, format="json")
        missing = self.client_b.post(f"{URL}{self.missing()}/move/", {"stage": "Won"}, format="json")

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, "New")
        self.assertIsNone(self.deal_a.closed_at)

    def test_delete_foreign_deal_is_like_a_missing_one(self):
        foreign = self.client_b.delete(f"{URL}{self.deal_a.id}/")
        missing = self.client_b.delete(f"{URL}{self.missing()}/")

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)
        self.deal_a.refresh_from_db()
        self.assertFalse(self.deal_a.is_deleted)

    def test_foreign_attempts_write_no_timeline_events(self):
        before = TimelineEvent.objects.count()

        self.client_b.patch(f"{URL}{self.deal_a.id}/", {"name": "x"}, format="json")
        self.client_b.post(f"{URL}{self.deal_a.id}/move/", {"stage": "Won"}, format="json")
        self.client_b.delete(f"{URL}{self.deal_a.id}/")

        self.assertEqual(TimelineEvent.objects.count(), before)

    def test_foreign_deal_timeline_is_not_found(self):
        response = self.client_b.get(f"/api/timeline/deals/{self.deal_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def payload(self, **overrides):
        data = {
            "name": "Cross-tenant deal",
            "owner_id": str(self.admin_b.id),
            "account_id": str(self.account_b.id),
        }
        data.update(overrides)
        return data

    def test_cannot_attach_another_companys_account(self):
        response = self.client_b.post(
            URL, self.payload(account_id=str(self.account_a.id)), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Selected account not found."})
        self.assertFalse(DjangoDealModel.objects.filter(name="Cross-tenant deal").exists())

    def test_cannot_attach_another_companys_contact(self):
        response = self.client_b.post(
            URL,
            self.payload(account_id=None, contact_id=str(self.contact_a.id)),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Selected contact not found."})
        self.assertFalse(DjangoDealModel.objects.filter(name="Cross-tenant deal").exists())

    def test_cannot_use_another_companys_user_as_owner(self):
        response = self.client_b.post(
            URL, self.payload(owner_id=str(self.admin_a.id)), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Deal owner does not exist."})

    def test_cannot_use_another_companys_lead_as_source(self):
        from src.modules.deals.deal_factories import make_lead

        lead_a = make_lead(self.company_a, self.admin_a, "Lead A")

        response = self.client_b.post(
            URL, self.payload(source_lead_id=str(lead_a.id)), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Selected lead not found."})

    def test_cannot_patch_in_another_companys_account_or_contact(self):
        own = self.client_b.get(URL).data["results"][0]["id"]

        by_account = self.client_b.patch(
            f"{URL}{own}/", {"account_id": str(self.account_a.id)}, format="json"
        )
        by_contact = self.client_b.patch(
            f"{URL}{own}/", {"contact_id": str(self.contact_a.id)}, format="json"
        )

        self.assertEqual(by_account.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(by_contact.status_code, status.HTTP_400_BAD_REQUEST)
        self.deal_b.refresh_from_db()
        self.assertEqual(self.deal_b.account_id, self.account_b.id)
        self.assertIsNone(self.deal_b.contact_id)

    def test_created_deal_belongs_to_the_callers_company(self):
        response = self.client_b.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        row = DjangoDealModel.objects.get(id=response.data["id"])
        self.assertEqual(row.company_id, self.company_b.id)
        self.assertEqual(self.client_a.get(URL).data["pagination"]["total"], 1)

    def test_repository_is_scoped_to_its_company(self):
        repo_b = DjangoDealRepository(company_id=self.company_b.id)

        self.assertIsNone(repo_b.get_by_id(self.deal_a.id))
        self.assertIsNone(repo_b.get_by_id_with_relations(self.deal_a.id))
        self.assertIsNotNone(repo_b.get_by_id(self.deal_b.id))

    def test_repository_requires_a_company(self):
        with self.assertRaises(ValueError):
            DjangoDealRepository(company_id=None)
