import uuid
from datetime import date
from decimal import Decimal

from rest_framework import status

from src.modules.deals.deal_factories import (
    DealApiTestBase,
    URL,
    make_account,
    make_deal,
    make_lead,
)
from src.modules.deals.infrastructure.persistence.models import DjangoDealModel
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

READ_FIELDS = {
    "id", "name", "amount", "expected_close_date", "stage", "probability",
    "owner_id", "owner_name", "account_id", "account_name", "contact_id",
    "contact_name", "source_lead_id", "source_lead_name", "lead_source",
    "description", "lost_reason", "closed_at", "created_by_id", "created_at",
    "updated_at",
}


class DealCrudTests(DealApiTestBase):
    def test_create_deal(self):
        response = self.create(
            contact_id=str(self.contact.id),
            expected_close_date="2026-12-31",
            description="First deal",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        body = response.data
        self.assertEqual(body["name"], "Big Deal")
        self.assertEqual(body["amount"], "100000.00")
        self.assertEqual(body["stage"], "New")
        self.assertEqual(body["probability"], 10)
        self.assertEqual(body["expected_close_date"], "2026-12-31")
        self.assertEqual(body["owner_id"], str(self.admin.id))
        self.assertEqual(body["created_by_id"], str(self.superadmin.id))
        self.assertIsNone(body["closed_at"])
        self.assertIsNone(body["lost_reason"])

        row = DjangoDealModel.objects.get(id=body["id"])
        self.assertEqual(row.company_id, self.company.id)
        self.assertEqual(row.amount, Decimal("100000.00"))
        self.assertFalse(row.is_deleted)

    def test_create_with_contact_only(self):
        response = self.create(account_id=None, contact_id=str(self.contact.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsNone(response.data["account_id"])
        self.assertEqual(response.data["contact_id"], str(self.contact.id))

    def test_amount_defaults_to_zero(self):
        data = self.payload()
        del data["amount"]

        response = self.client.post(URL, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["amount"], "0.00")

    def test_create_from_source_lead_copies_lead_source(self):
        lead = make_lead(self.company, self.admin, "Hot Lead", lead_source="Referral")

        response = self.create(source_lead_id=str(lead.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["source_lead_id"], str(lead.id))
        self.assertEqual(response.data["lead_source"], "Referral")

    def test_read_detail_has_names_and_every_field(self):
        lead = make_lead(self.company, self.admin, "Hot Lead", lead_source="Referral")
        created = self.create(
            contact_id=str(self.contact.id), source_lead_id=str(lead.id)
        ).data

        response = self.client.get(f"{URL}{created['id']}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), READ_FIELDS)
        self.assertEqual(response.data["owner_name"], "Admin A")
        self.assertEqual(response.data["account_name"], "Acme Corp")
        self.assertEqual(response.data["contact_name"], "Jane Doe")
        self.assertEqual(response.data["source_lead_name"], "Hot Lead")
        self.assertEqual(response.data["amount"], "100000.00")

    def test_read_unknown_deal_is_404(self):
        response = self.client.get(f"{URL}{uuid.uuid4()}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"detail": "Deal not found."})

    def test_list_shape(self):
        self.create()

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"results", "pagination"})
        self.assertEqual(
            response.data["pagination"],
            {"page": 1, "page_size": 20, "total": 1, "total_pages": 1},
        )
        self.assertEqual(set(response.data["results"][0]), READ_FIELDS)

    def test_patch_updates_only_sent_fields(self):
        deal_id = self.create(description="keep me").data["id"]

        response = self.client.patch(
            f"{URL}{deal_id}/",
            {"name": "Renamed", "amount": "250.50"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["name"], "Renamed")
        self.assertEqual(response.data["amount"], "250.50")
        self.assertEqual(response.data["description"], "keep me")
        row = DjangoDealModel.objects.get(id=deal_id)
        self.assertEqual(row.name, "Renamed")
        self.assertEqual(row.amount, Decimal("250.50"))
        self.assertEqual(row.account_id, self.account.id)

    def test_patch_can_change_owner_account_and_date(self):
        other_account = make_account(self.company, self.admin, "Other Corp")
        deal_id = self.create().data["id"]

        response = self.client.patch(
            f"{URL}{deal_id}/",
            {
                "owner_id": str(self.superadmin.id),
                "account_id": str(other_account.id),
                "expected_close_date": "2020-01-01",  # past dates are allowed
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["owner_id"], str(self.superadmin.id))
        self.assertEqual(response.data["account_id"], str(other_account.id))
        self.assertEqual(response.data["expected_close_date"], "2020-01-01")

    def test_patch_unknown_deal_is_rejected(self):
        response = self.client.patch(
            f"{URL}{uuid.uuid4()}/", {"name": "x"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Deal not found."})

    def test_soft_delete(self):
        deal_id = self.create().data["id"]

        response = self.client.delete(f"{URL}{deal_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": "Deal deleted successfully."})
        row = DjangoDealModel.objects.get(id=deal_id)  # row is kept
        self.assertTrue(row.is_deleted)

    def test_deleted_deal_is_hidden_from_list_and_detail(self):
        deal_id = self.create().data["id"]
        self.client.delete(f"{URL}{deal_id}/")

        listing = self.client.get(URL)
        detail = self.client.get(f"{URL}{deal_id}/")

        self.assertEqual(listing.data["results"], [])
        self.assertEqual(listing.data["pagination"]["total"], 0)
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_deal_cannot_be_updated_moved_or_deleted_again(self):
        deal_id = self.create().data["id"]
        self.client.delete(f"{URL}{deal_id}/")

        patch = self.client.patch(f"{URL}{deal_id}/", {"name": "x"}, format="json")
        move = self.client.post(f"{URL}{deal_id}/move/", {"stage": "Won"}, format="json")
        again = self.client.delete(f"{URL}{deal_id}/")

        for response in (patch, move, again):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, {"detail": "Deal not found."})

    def test_requires_authentication(self):
        from rest_framework.test import APIClient

        self.assertEqual(
            APIClient().get(URL).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_platform_superadmin_has_no_access(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "platform@example.com")

        response = authenticated_client(platform).get(URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DealValidationTests(DealApiTestBase):
    def assert_rejected(self, response, text):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(set(response.data), {"detail"})
        self.assertIn(text, response.data["detail"])
        self.assertEqual(DjangoDealModel.objects.count(), 0)

    def test_blank_name(self):
        self.assert_rejected(self.create(name="   "), "name is required")

    def test_missing_name(self):
        data = self.payload()
        del data["name"]

        self.assert_rejected(
            self.client.post(URL, data, format="json"), "name"
        )

    def test_negative_amount(self):
        self.assert_rejected(self.create(amount="-1.00"), "greater than or equal to 0")

    def test_amount_with_too_many_decimals(self):
        self.assert_rejected(self.create(amount="1.234"), "amount")

    def test_inactive_owner(self):
        inactive = make_user(self.company, User.Role.ADMIN, "off@a.example.com", is_active=False)

        self.assert_rejected(self.create(owner_id=str(inactive.id)), "inactive")

    def test_non_admin_owner(self):
        rep = make_user(self.company, User.Role.SALES_EXECUTIVE, "rep@a.example.com")

        self.assert_rejected(self.create(owner_id=str(rep.id)), "ADMIN or SUPERADMIN")

    def test_unknown_owner(self):
        self.assert_rejected(self.create(owner_id=str(uuid.uuid4())), "owner does not exist")

    def test_deleted_account(self):
        self.account.is_deleted = True
        self.account.save()

        self.assert_rejected(self.create(), "account not found")

    def test_deleted_contact(self):
        self.contact.is_deleted = True
        self.contact.save()

        self.assert_rejected(
            self.create(account_id=None, contact_id=str(self.contact.id)),
            "contact not found",
        )

    def test_contact_of_a_different_account(self):
        other_account = make_account(self.company, self.admin, "Other Corp")

        self.assert_rejected(
            self.create(
                account_id=str(other_account.id), contact_id=str(self.contact.id)
            ),
            "does not belong to the selected account",
        )

    def test_neither_account_nor_contact(self):
        self.assert_rejected(
            self.create(account_id=None, contact_id=None), "account or a contact"
        )

    def test_probability_out_of_range(self):
        self.assert_rejected(self.create(probability=101), "between 0 and 100")
        self.assert_rejected(self.create(probability=-1), "between 0 and 100")

    def test_probability_not_an_integer(self):
        self.assert_rejected(self.create(probability="abc"), "probability")
        self.assert_rejected(self.create(probability=50.5), "probability")

    def test_unknown_stage(self):
        self.assert_rejected(self.create(stage="Maybe"), "stage")

    def test_create_as_lost_needs_a_reason(self):
        self.assert_rejected(self.create(stage="Lost"), "lost reason")

    def test_patch_validation(self):
        deal_id = self.create().data["id"]
        other_company = make_company("Other", "other")
        stranger = make_user(other_company, User.Role.ADMIN, "stranger@o.example.com")

        for body, text in [
            ({"name": " "}, "name is required"),
            ({"amount": "-5"}, "greater than or equal to 0"),
            ({"owner_id": str(stranger.id)}, "owner does not exist"),
            ({"account_id": None}, "account or a contact"),
            ({"probability": 150}, "between 0 and 100"),
        ]:
            with self.subTest(body=body):
                response = self.client.patch(f"{URL}{deal_id}/", body, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(text, response.data["detail"])

        row = DjangoDealModel.objects.get(id=deal_id)
        self.assertEqual(row.name, "Big Deal")
        self.assertEqual(row.account_id, self.account.id)

    def test_patch_contact_mismatch(self):
        other_account = make_account(self.company, self.admin, "Other Corp")
        deal_id = self.create().data["id"]

        response = self.client.patch(
            f"{URL}{deal_id}/",
            {
                "account_id": str(other_account.id),
                "contact_id": str(self.contact.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not belong", response.data["detail"])


class DealListQueryTests(DealApiTestBase):
    def setUp(self):
        super().setUp()
        self.other_account = make_account(self.company, self.admin, "Globex")
        self.d_alpha = make_deal(
            self.company, self.admin, account=self.account, name="Alpha Rollout",
            amount=Decimal("500.00"), stage="New", probability=10,
            expected_close_date=date(2026, 1, 10),
        )
        self.d_bravo = make_deal(
            self.company, self.superadmin, account=self.other_account,
            contact=None, name="bravo upgrade", amount=Decimal("1500.00"),
            stage="Negotiation", probability=70,
            expected_close_date=date(2026, 3, 10),
        )
        self.d_charlie = make_deal(
            self.company, self.admin, contact=self.contact, name="Charlie Renewal",
            amount=Decimal("2500.00"), stage="Won", probability=100,
            expected_close_date=None,
        )

    def names(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [row["name"] for row in response.data["results"]]

    def filtered(self, *filters, **params):
        import json

        return self.client.get(URL, {"filters": json.dumps(list(filters)), **params})

    def test_default_order_is_newest_first(self):
        self.assertEqual(
            self.names(self.client.get(URL)),
            ["Charlie Renewal", "bravo upgrade", "Alpha Rollout"],
        )

    def test_filter_by_stage(self):
        response = self.filtered({"field": "stage", "operator": "equals", "value": "Won"})
        self.assertEqual(self.names(response), ["Charlie Renewal"])

        response = self.filtered(
            {"field": "stage", "operator": "in", "value": ["New", "Negotiation"]}
        )
        self.assertCountEqual(self.names(response), ["Alpha Rollout", "bravo upgrade"])

    def test_filter_by_owner_account_and_contact(self):
        response = self.filtered(
            {"field": "owner", "operator": "equals", "value": str(self.superadmin.id)}
        )
        self.assertEqual(self.names(response), ["bravo upgrade"])

        response = self.filtered(
            {"field": "account", "operator": "equals", "value": str(self.account.id)}
        )
        self.assertEqual(self.names(response), ["Alpha Rollout"])

        response = self.filtered(
            {"field": "contact", "operator": "equals", "value": str(self.contact.id)}
        )
        self.assertEqual(self.names(response), ["Charlie Renewal"])

    def test_filter_by_close_date_range(self):
        response = self.filtered(
            {
                "field": "expected_close_date",
                "operator": "between",
                "value": {"from": "2026-01-01", "to": "2026-02-28"},
            }
        )
        self.assertEqual(self.names(response), ["Alpha Rollout"])

    def test_filter_by_amount_range(self):
        response = self.filtered(
            {
                "field": "amount",
                "operator": "between",
                "value": {"from": "1000", "to": "2000"},
            }
        )
        self.assertEqual(self.names(response), ["bravo upgrade"])

        response = self.filtered(
            {"field": "amount", "operator": "greater_than", "value": 1500}
        )
        self.assertEqual(self.names(response), ["Charlie Renewal"])

    def test_name_search_and_name_filter(self):
        self.assertEqual(
            self.names(self.client.get(URL, {"search": "UPGRADE"})), ["bravo upgrade"]
        )
        response = self.filtered(
            {"field": "name", "operator": "starts_with", "value": "alp"}
        )
        self.assertEqual(self.names(response), ["Alpha Rollout"])

    def test_invalid_filters_are_400(self):
        for filters in (
            [{"field": "nope", "operator": "equals", "value": "x"}],
            [{"field": "stage", "operator": "equals", "value": "Maybe"}],
            [{"field": "amount", "operator": "between", "value": {"from": "x", "to": "1"}}],
            [{"field": "owner", "operator": "equals", "value": "not-a-uuid"}],
        ):
            with self.subTest(filters=filters):
                response = self.filtered(*filters)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("detail", response.data)

    def test_sorting(self):
        cases = {
            "name": ["Alpha Rollout", "bravo upgrade", "Charlie Renewal"],  # case-insensitive
            "amount": ["Alpha Rollout", "bravo upgrade", "Charlie Renewal"],
            "probability": ["Alpha Rollout", "bravo upgrade", "Charlie Renewal"],
            "stage": ["bravo upgrade", "Alpha Rollout", "Charlie Renewal"],
            "created_at": ["Alpha Rollout", "bravo upgrade", "Charlie Renewal"],
        }
        for sort_by, expected in cases.items():
            with self.subTest(sort_by=sort_by, direction="asc"):
                response = self.client.get(URL, {"sort_by": sort_by, "sort_direction": "asc"})
                self.assertEqual(self.names(response), expected)
            with self.subTest(sort_by=sort_by, direction="desc"):
                response = self.client.get(URL, {"sort_by": sort_by, "sort_direction": "desc"})
                self.assertEqual(self.names(response), list(reversed(expected)))

    def test_sort_by_owner(self):
        # "Admin A" owns two deals, "Super A" owns bravo.
        asc = self.names(self.client.get(URL, {"sort_by": "owner", "sort_direction": "asc"}))
        desc = self.names(self.client.get(URL, {"sort_by": "owner", "sort_direction": "desc"}))

        self.assertEqual(asc[-1], "bravo upgrade")
        self.assertEqual(desc[0], "bravo upgrade")

    def test_sort_by_close_date_puts_empty_dates_last(self):
        asc = self.client.get(URL, {"sort_by": "expected_close_date", "sort_direction": "asc"})
        desc = self.client.get(URL, {"sort_by": "expected_close_date", "sort_direction": "desc"})

        self.assertEqual(self.names(asc), ["Alpha Rollout", "bravo upgrade", "Charlie Renewal"])
        self.assertEqual(self.names(desc), ["bravo upgrade", "Alpha Rollout", "Charlie Renewal"])

    def test_unsupported_sort_is_400(self):
        response = self.client.get(URL, {"sort_by": "lost_reason"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pagination(self):
        first = self.client.get(URL, {"page_size": 2, "sort_by": "name", "sort_direction": "asc"})
        second = self.client.get(URL, {"page": 2, "page_size": 2, "sort_by": "name", "sort_direction": "asc"})

        self.assertEqual(self.names(first), ["Alpha Rollout", "bravo upgrade"])
        self.assertEqual(self.names(second), ["Charlie Renewal"])
        self.assertEqual(
            first.data["pagination"],
            {"page": 1, "page_size": 2, "total": 3, "total_pages": 2},
        )

    def test_pagination_errors_and_empty_page(self):
        self.assertEqual(
            self.client.get(URL, {"page_size": 51}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        beyond = self.client.get(URL, {"page": 9})
        self.assertEqual(beyond.data["results"], [])
        self.assertEqual(beyond.data["pagination"]["total"], 3)

    def test_deleted_deals_are_not_counted(self):
        self.d_alpha.is_deleted = True
        self.d_alpha.save()

        response = self.client.get(URL)

        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertNotIn("Alpha Rollout", self.names(response))
