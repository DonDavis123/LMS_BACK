from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from src.modules.deals.deal_factories import (
    DealApiTestBase,
    make_account,
    make_contact,
    make_deal,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

BOARD = "/api/deals/board/"

STAGES = ["New", "Quotation Sent", "Negotiation", "Won", "Lost"]
DEFAULT_PROBABILITIES = [10, 40, 70, 100, 0]

CARD_FIELDS = {
    "id", "name", "amount", "expected_close_date", "probability",
    "owner_id", "owner_name", "account_id", "account_name",
    "contact_id", "contact_name",
}
COLUMN_FIELDS = {
    "stage", "default_probability", "count", "total_amount",
    "weighted_amount", "has_more", "deals",
}


class DealBoardBase(DealApiTestBase):
    def board(self, client=None, **params):
        return (client or self.client).get(BOARD, params)

    @staticmethod
    def column(response, stage):
        return next(c for c in response.data["stages"] if c["stage"] == stage)

    def seed(self, stage, count=1, name=None, **extra):
        """Deals of the account; Won / Lost deals get a recent ``closed_at``."""
        if stage in ("Won", "Lost"):
            extra.setdefault("closed_at", timezone.now() - timedelta(days=3))

        return [
            make_deal(
                self.company, self.admin, account=self.account,
                name=name if name is not None else f"{stage} deal {i}",
                stage=stage, **extra,
            )
            for i in range(count)
        ]


class DealBoardShapeTests(DealBoardBase):
    def test_all_five_stages_are_returned_in_order_even_when_empty(self):
        response = self.board()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(set(response.data), {"stages"})
        self.assertEqual([c["stage"] for c in response.data["stages"]], STAGES)
        self.assertEqual(
            [c["default_probability"] for c in response.data["stages"]],
            DEFAULT_PROBABILITIES,
        )

        for column in response.data["stages"]:
            self.assertEqual(set(column), COLUMN_FIELDS)
            self.assertEqual(column["count"], 0)
            self.assertEqual(column["total_amount"], "0.00")
            self.assertEqual(column["weighted_amount"], "0.00")
            self.assertFalse(column["has_more"])
            self.assertEqual(column["deals"], [])

    def test_card_has_the_documented_fields(self):
        deal = make_deal(
            self.company, self.admin, account=self.account, contact=self.contact,
            name="Website for Ravi's shop", amount=Decimal("100000.00"),
            stage="Quotation Sent", probability=40,
            expected_close_date=date(2026, 11, 30),
        )

        response = self.board()

        column = self.column(response, "Quotation Sent")
        self.assertEqual(len(column["deals"]), 1)
        card = column["deals"][0]
        self.assertEqual(set(card), CARD_FIELDS)
        self.assertEqual(card["id"], str(deal.id))
        self.assertEqual(card["name"], "Website for Ravi's shop")
        self.assertEqual(card["amount"], "100000.00")
        self.assertEqual(card["expected_close_date"], "2026-11-30")
        self.assertEqual(card["probability"], 40)
        self.assertEqual(card["owner_id"], str(self.admin.id))
        self.assertEqual(card["owner_name"], "Admin A")
        self.assertEqual(card["account_id"], str(self.account.id))
        self.assertEqual(card["account_name"], "Acme Corp")
        self.assertEqual(card["contact_id"], str(self.contact.id))
        self.assertEqual(card["contact_name"], "Jane Doe")

    def test_card_without_account_or_contact_has_null_names(self):
        make_deal(
            self.company, self.admin, account=None, contact=self.contact,
            name="Contact only",
        )

        card = self.column(self.board(), "New")["deals"][0]

        self.assertIsNone(card["account_id"])
        self.assertIsNone(card["account_name"])
        self.assertEqual(card["contact_name"], "Jane Doe")
        self.assertIsNone(card["expected_close_date"])


class DealBoardTotalsTests(DealBoardBase):
    def test_counts_and_totals_per_column(self):
        self.seed("New", amount=Decimal("50000"), name="N1")
        self.seed("New", amount=Decimal("30000"), name="N2")
        self.seed("Quotation Sent", amount=Decimal("100000"), probability=40)
        self.seed("Negotiation", amount=Decimal("250000"), probability=70, name="G1")
        self.seed("Negotiation", amount=Decimal("75000"), probability=70, name="G2")
        self.seed("Won", amount=Decimal("80000"), probability=100)
        self.seed("Lost", amount=Decimal("20000"), probability=0)

        response = self.board()

        expected = {
            "New": (2, "80000.00", "8000.00"),
            "Quotation Sent": (1, "100000.00", "40000.00"),
            "Negotiation": (2, "325000.00", "227500.00"),
            "Won": (1, "80000.00", "80000.00"),
            "Lost": (1, "20000.00", "0.00"),
        }
        for stage, (count, total, weighted) in expected.items():
            column = self.column(response, stage)
            self.assertEqual(column["count"], count, stage)
            self.assertEqual(column["total_amount"], total, stage)
            self.assertEqual(column["weighted_amount"], weighted, stage)
            self.assertEqual(len(column["deals"]), count, stage)
            self.assertFalse(column["has_more"], stage)

    def test_weighted_amount_uses_the_deals_own_probability(self):
        self.seed("New", amount=Decimal("100000"), probability=55)

        column = self.column(self.board(), "New")

        self.assertEqual(column["weighted_amount"], "55000.00")

    def test_deleted_deals_are_excluded(self):
        self.seed("New", amount=Decimal("1000"), name="Live")
        self.seed("New", amount=Decimal("9000"), name="Gone", is_deleted=True)

        column = self.column(self.board(), "New")

        self.assertEqual(column["count"], 1)
        self.assertEqual(column["total_amount"], "1000.00")
        self.assertEqual([d["name"] for d in column["deals"]], ["Live"])


class DealBoardCapTests(DealBoardBase):
    def seed_dated(self, stage, count):
        start = date(2026, 1, 1)
        for i in range(count):
            make_deal(
                self.company, self.admin, account=self.account,
                name=f"Deal {i:02d}", stage=stage, amount=Decimal("100"),
                expected_close_date=start + timedelta(days=i),
            )

    def test_cards_are_capped_at_50_with_has_more_but_totals_cover_all(self):
        self.seed_dated("New", 52)

        column = self.column(self.board(), "New")

        self.assertEqual(column["count"], 52)
        self.assertEqual(column["total_amount"], "5200.00")
        self.assertEqual(column["weighted_amount"], "520.00")
        self.assertEqual(len(column["deals"]), 50)
        self.assertTrue(column["has_more"])

        # Soonest expected close date first: the two latest are cut off.
        names = [d["name"] for d in column["deals"]]
        self.assertEqual(names[0], "Deal 00")
        self.assertEqual(names[-1], "Deal 49")
        self.assertNotIn("Deal 50", names)
        self.assertNotIn("Deal 51", names)

    def test_exactly_50_deals_is_not_truncated(self):
        self.seed_dated("New", 50)

        column = self.column(self.board(), "New")

        self.assertEqual(column["count"], 50)
        self.assertEqual(len(column["deals"]), 50)
        self.assertFalse(column["has_more"])

    def test_cap_is_per_column(self):
        self.seed_dated("New", 51)
        self.seed("Negotiation", count=3)

        response = self.board()

        self.assertTrue(self.column(response, "New")["has_more"])
        self.assertFalse(self.column(response, "Negotiation")["has_more"])
        self.assertEqual(len(self.column(response, "Negotiation")["deals"]), 3)

    def test_closed_column_cap_keeps_the_newest(self):
        now = timezone.now()
        for i in range(52):
            make_deal(
                self.company, self.admin, account=self.account,
                name=f"Won {i:02d}", stage="Won", probability=100,
                closed_at=now - timedelta(hours=i + 1),
            )

        column = self.column(self.board(), "Won")

        self.assertEqual(column["count"], 52)
        self.assertEqual(len(column["deals"]), 50)
        self.assertTrue(column["has_more"])
        names = [d["name"] for d in column["deals"]]
        self.assertEqual(names[0], "Won 00")
        self.assertNotIn("Won 51", names)

    def test_query_count_does_not_grow_with_the_number_of_deals(self):
        self.seed("New", count=1)
        self.seed("Negotiation", count=1)
        self.seed("Won", count=1)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.board().status_code, status.HTTP_200_OK)

        for stage in ("New", "Quotation Sent", "Negotiation", "Won", "Lost"):
            for i in range(8):
                make_deal(
                    self.company, self.admin, account=self.account,
                    contact=self.contact, name=f"Extra {stage} {i}", stage=stage,
                    closed_at=timezone.now() - timedelta(days=1)
                    if stage in ("Won", "Lost") else None,
                )
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.board().status_code, status.HTTP_200_OK)

        self.assertEqual(len(large), len(small))


class DealBoardOrderTests(DealBoardBase):
    def test_open_column_is_soonest_close_date_first_with_undated_last(self):
        make_deal(self.company, self.admin, account=self.account, name="Dec",
                  expected_close_date=date(2026, 12, 1))
        make_deal(self.company, self.admin, account=self.account, name="Undated")
        make_deal(self.company, self.admin, account=self.account, name="Nov",
                  expected_close_date=date(2026, 11, 1))

        column = self.column(self.board(), "New")

        self.assertEqual([d["name"] for d in column["deals"]], ["Nov", "Dec", "Undated"])

    def test_won_and_lost_columns_are_newest_first(self):
        now = timezone.now()
        for name, days in (("old", 10), ("newest", 1), ("middle", 5)):
            make_deal(self.company, self.admin, account=self.account, name=name,
                      stage="Won", probability=100,
                      closed_at=now - timedelta(days=days))
            make_deal(self.company, self.admin, account=self.account, name=name,
                      stage="Lost", probability=0, lost_reason="Price",
                      closed_at=now - timedelta(days=days))

        response = self.board()

        for stage in ("Won", "Lost"):
            self.assertEqual(
                [d["name"] for d in self.column(response, stage)["deals"]],
                ["newest", "middle", "old"],
                stage,
            )


class DealBoardFilterTests(DealBoardBase):
    def test_owner_id_filter(self):
        make_deal(self.company, self.admin, account=self.account, name="Admin deal",
                  amount=Decimal("100"))
        make_deal(self.company, self.superadmin, account=self.account,
                  name="Super deal", amount=Decimal("300"))

        response = self.board(owner_id=str(self.superadmin.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        column = self.column(response, "New")
        self.assertEqual(column["count"], 1)
        self.assertEqual(column["total_amount"], "300.00")
        self.assertEqual([d["name"] for d in column["deals"]], ["Super deal"])

    def test_expected_close_range_is_inclusive(self):
        for name, day in (("before", date(2026, 10, 31)), ("first", date(2026, 11, 1)),
                          ("last", date(2026, 11, 30)), ("after", date(2026, 12, 1))):
            make_deal(self.company, self.admin, account=self.account, name=name,
                      expected_close_date=day)
        make_deal(self.company, self.admin, account=self.account, name="undated")

        response = self.board(
            expected_close_from="2026-11-01", expected_close_to="2026-11-30",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            sorted(d["name"] for d in self.column(response, "New")["deals"]),
            ["first", "last"],
        )

    def test_expected_close_from_alone(self):
        make_deal(self.company, self.admin, account=self.account, name="early",
                  expected_close_date=date(2026, 10, 1))
        make_deal(self.company, self.admin, account=self.account, name="late",
                  expected_close_date=date(2026, 12, 1))

        response = self.board(expected_close_from="2026-11-01")

        self.assertEqual(
            [d["name"] for d in self.column(response, "New")["deals"]], ["late"],
        )

    def test_search_matches_the_name_case_insensitively(self):
        make_deal(self.company, self.admin, account=self.account,
                  name="Website for Ravi's shop")
        make_deal(self.company, self.admin, account=self.account, name="Mobile app")

        response = self.board(search="WEBSITE")

        column = self.column(response, "New")
        self.assertEqual(column["count"], 1)
        self.assertEqual(column["deals"][0]["name"], "Website for Ravi's shop")

    def test_blank_search_is_ignored(self):
        make_deal(self.company, self.admin, account=self.account, name="Anything")

        response = self.board(search="   ")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.column(response, "New")["count"], 1)

    def test_filters_apply_to_totals_too(self):
        make_deal(self.company, self.admin, account=self.account, name="Match",
                  amount=Decimal("100"))
        make_deal(self.company, self.admin, account=self.account, name="Other",
                  amount=Decimal("900"))

        column = self.column(self.board(search="Match"), "New")

        self.assertEqual(column["count"], 1)
        self.assertEqual(column["total_amount"], "100.00")


class DealBoardClosedWindowTests(DealBoardBase):
    def seed_closed(self, stage, name, days_ago):
        make_deal(
            self.company, self.admin, account=self.account, name=name,
            stage=stage, probability=100 if stage == "Won" else 0,
            closed_at=timezone.now() - timedelta(days=days_ago),
        )

    def test_default_window_is_30_days_for_won_and_lost(self):
        self.seed_closed("Won", "won recent", 10)
        self.seed_closed("Won", "won old", 40)
        self.seed_closed("Lost", "lost recent", 29)
        self.seed_closed("Lost", "lost old", 31)

        response = self.board()

        self.assertEqual(
            [d["name"] for d in self.column(response, "Won")["deals"]], ["won recent"],
        )
        self.assertEqual(
            [d["name"] for d in self.column(response, "Lost")["deals"]], ["lost recent"],
        )
        self.assertEqual(self.column(response, "Won")["count"], 1)
        self.assertEqual(self.column(response, "Lost")["count"], 1)

    def test_closed_within_days_widens_and_narrows_the_window(self):
        self.seed_closed("Won", "ten days", 10)
        self.seed_closed("Won", "forty days", 40)

        wide = self.board(closed_within_days=60)
        narrow = self.board(closed_within_days=5)

        self.assertEqual(self.column(wide, "Won")["count"], 2)
        self.assertEqual(self.column(narrow, "Won")["count"], 0)
        self.assertEqual(self.column(narrow, "Won")["total_amount"], "0.00")

    def test_closed_within_days_does_not_affect_open_stages(self):
        make_deal(self.company, self.admin, account=self.account, name="Open",
                  stage="Negotiation", probability=70)
        make_deal(self.company, self.admin, account=self.account, name="Fresh",
                  stage="New")

        response = self.board(closed_within_days=1)

        self.assertEqual(self.column(response, "New")["count"], 1)
        self.assertEqual(self.column(response, "Negotiation")["count"], 1)

    def test_closed_deal_without_closed_at_is_not_shown(self):
        make_deal(self.company, self.admin, account=self.account, name="No date",
                  stage="Won", probability=100, closed_at=None)

        self.assertEqual(self.column(self.board(), "Won")["count"], 0)


class DealBoardValidationTests(DealBoardBase):
    def assert_bad_request(self, **params):
        response = self.board(**params)

        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, (params, response.data),
        )
        self.assertEqual(set(response.data), {"detail"}, params)
        self.assertTrue(response.data["detail"], params)

    def test_invalid_params_return_400_with_detail(self):
        self.assert_bad_request(owner_id="not-a-uuid")
        self.assert_bad_request(expected_close_from="31-12-2026")
        self.assert_bad_request(expected_close_to="2026-02-30")
        self.assert_bad_request(closed_within_days="abc")
        self.assert_bad_request(closed_within_days="0")
        self.assert_bad_request(closed_within_days="-5")
        self.assert_bad_request(closed_within_days="99999")

    def test_from_after_to_is_rejected(self):
        self.assert_bad_request(
            expected_close_from="2026-12-01", expected_close_to="2026-11-01",
        )

    def test_anonymous_request_is_rejected(self):
        response = APIClient().get(BOARD)

        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )


class DealBoardTenantIsolationTests(DealBoardBase):
    def setUp(self):
        super().setUp()
        self.company_b = make_company("Company B", "company-b")
        self.admin_b = make_user(
            self.company_b, User.Role.ADMIN, "admin@b.example.com", name="Admin B",
        )
        self.superadmin_b = make_user(
            self.company_b, User.Role.SUPERADMIN, "super@b.example.com",
        )
        self.account_b = make_account(self.company_b, self.admin_b, "Beta Corp")
        self.contact_b = make_contact(self.company_b, self.admin_b, "Bob", self.account_b)
        self.client_b = authenticated_client(self.superadmin_b)

        make_deal(self.company, self.admin, account=self.account, name="A open",
                  amount=Decimal("1000"))
        make_deal(self.company_b, self.admin_b, account=self.account_b,
                  name="B open", amount=Decimal("7000"))
        make_deal(self.company_b, self.admin_b, account=self.account_b,
                  name="B won", stage="Won", probability=100, amount=Decimal("5000"),
                  closed_at=timezone.now() - timedelta(days=1))

    def test_each_company_sees_only_its_own_deals(self):
        response_a = self.board()
        response_b = self.board(client=self.client_b)

        new_a = self.column(response_a, "New")
        self.assertEqual([d["name"] for d in new_a["deals"]], ["A open"])
        self.assertEqual(new_a["total_amount"], "1000.00")
        self.assertEqual(self.column(response_a, "Won")["count"], 0)

        new_b = self.column(response_b, "New")
        self.assertEqual([d["name"] for d in new_b["deals"]], ["B open"])
        self.assertEqual(new_b["total_amount"], "7000.00")
        self.assertEqual(self.column(response_b, "Won")["count"], 1)

    def test_owner_filter_cannot_reach_another_companys_deals(self):
        response = self.board(owner_id=str(self.admin_b.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        for column in response.data["stages"]:
            self.assertEqual(column["count"], 0, column["stage"])
            self.assertEqual(column["deals"], [], column["stage"])
