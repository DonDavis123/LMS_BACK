from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from src.modules.deals.application.dto.deal_forecast import DealForecastQuery
from src.modules.deals.application.use_cases.get_deal_forecast import (
    GetDealForecastUseCase,
    month_bounds,
)
from src.modules.deals.deal_factories import (
    DealApiTestBase,
    make_account,
    make_deal,
)
from src.modules.deals.infrastructure.persistence.django_deal_repository import (
    DjangoDealRepository,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

FORECAST = "/api/deals/forecast/"
CLOCK = "src.modules.deals.application.use_cases.get_deal_forecast._utcnow"

# 18 Nov 2026, noon in Kolkata: "this month" is November 2026 everywhere.
NOW = datetime(2026, 11, 18, 6, 30, tzinfo=dt_timezone.utc)
THIS_MONTH = datetime(2026, 11, 10, 9, 0, tzinfo=dt_timezone.utc)
LAST_MONTH = datetime(2026, 10, 10, 9, 0, tzinfo=dt_timezone.utc)

FORECAST_FIELDS = {
    "open_pipeline", "weighted_forecast", "won_this_month", "lost_this_month",
    "open_deal_count", "by_stage", "by_month",
}
OPEN_STAGES = ["New", "Quotation Sent", "Negotiation"]


class DealForecastBase(DealApiTestBase):
    def forecast(self, client=None, now=NOW, **params):
        with patch(CLOCK, return_value=now):
            return (client or self.client).get(FORECAST, params)

    def deal(self, stage="New", amount="1000", owner=None, **extra):
        extra.setdefault("name", f"{stage} {amount}")
        return make_deal(
            self.company, owner or self.admin, account=self.account,
            stage=stage, amount=Decimal(amount), **extra,
        )

    def seed_spec_fixture(self):
        """New (10%): 50,000 + 30,000; Quotation Sent (40%): 1,00,000;
        Negotiation (70%): 2,50,000 + 75,000; Won this month: 80,000."""
        close = date(2026, 11, 30)
        self.deal("New", "50000", probability=10, expected_close_date=close)
        self.deal("New", "30000", probability=10, expected_close_date=close)
        self.deal("Quotation Sent", "100000", probability=40, expected_close_date=close)
        self.deal("Negotiation", "250000", probability=70, expected_close_date=close)
        self.deal("Negotiation", "75000", probability=70, expected_close_date=close)
        self.deal("Won", "80000", probability=100, closed_at=THIS_MONTH)


class DealForecastDefinitionTests(DealForecastBase):
    def test_exact_fixture_from_the_spec(self):
        self.seed_spec_fixture()

        response = self.forecast()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(set(response.data), FORECAST_FIELDS)
        self.assertEqual(response.data["open_pipeline"], "505000.00")
        self.assertEqual(response.data["weighted_forecast"], "275500.00")
        self.assertEqual(response.data["won_this_month"], "80000.00")
        self.assertEqual(response.data["lost_this_month"], "0.00")
        self.assertEqual(response.data["open_deal_count"], 5)

        self.assertEqual(
            [dict(row) for row in response.data["by_stage"]],
            [
                {"stage": "New", "count": 2,
                 "total_amount": "80000.00", "weighted_amount": "8000.00"},
                {"stage": "Quotation Sent", "count": 1,
                 "total_amount": "100000.00", "weighted_amount": "40000.00"},
                {"stage": "Negotiation", "count": 2,
                 "total_amount": "325000.00", "weighted_amount": "227500.00"},
            ],
        )
        self.assertEqual(
            [dict(row) for row in response.data["by_month"]],
            [{"month": "2026-11", "total_amount": "505000.00",
              "weighted_amount": "275500.00"}],
        )

    def test_custom_probability_overrides_the_stage_default(self):
        # A New deal normally weighs 10%; this one was set to 55%.
        self.deal("New", "100000", probability=55)

        response = self.forecast()

        self.assertEqual(response.data["open_pipeline"], "100000.00")
        self.assertEqual(response.data["weighted_forecast"], "55000.00")
        self.assertEqual(response.data["by_stage"][0]["weighted_amount"], "55000.00")
        self.assertEqual(response.data["by_month"][0]["weighted_amount"], "55000.00")

    def test_zero_probability_open_deal_counts_in_pipeline_not_forecast(self):
        self.deal("Negotiation", "40000", probability=0)

        response = self.forecast()

        self.assertEqual(response.data["open_pipeline"], "40000.00")
        self.assertEqual(response.data["weighted_forecast"], "0.00")
        self.assertEqual(response.data["open_deal_count"], 1)

    def test_won_and_lost_are_not_part_of_the_open_pipeline(self):
        self.deal("New", "1000", probability=10)
        self.deal("Won", "5000", probability=100, closed_at=THIS_MONTH)
        self.deal("Lost", "700", probability=0, closed_at=THIS_MONTH,
                  lost_reason="Price")

        response = self.forecast()

        self.assertEqual(response.data["open_pipeline"], "1000.00")
        self.assertEqual(response.data["weighted_forecast"], "100.00")
        self.assertEqual(response.data["open_deal_count"], 1)
        self.assertEqual(response.data["won_this_month"], "5000.00")
        self.assertEqual(response.data["lost_this_month"], "700.00")

    def test_won_and_lost_of_other_months_are_ignored(self):
        self.deal("Won", "5000", probability=100, closed_at=LAST_MONTH)
        self.deal("Lost", "700", probability=0, closed_at=LAST_MONTH,
                  lost_reason="Price")
        self.deal("Won", "9000", probability=100,
                  closed_at=datetime(2026, 12, 2, 9, 0, tzinfo=dt_timezone.utc))
        self.deal("Won", "123", probability=100, closed_at=None)

        response = self.forecast()

        self.assertEqual(response.data["won_this_month"], "0.00")
        self.assertEqual(response.data["lost_this_month"], "0.00")

    def test_empty_company_returns_zeroes(self):
        response = self.forecast()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["open_pipeline"], "0.00")
        self.assertEqual(response.data["weighted_forecast"], "0.00")
        self.assertEqual(response.data["won_this_month"], "0.00")
        self.assertEqual(response.data["lost_this_month"], "0.00")
        self.assertEqual(response.data["open_deal_count"], 0)
        self.assertEqual(response.data["by_month"], [])
        self.assertEqual(len(response.data["by_stage"]), 3)

    def test_deleted_deals_are_excluded(self):
        self.deal("New", "1000", probability=10)
        self.deal("New", "9000", probability=10, is_deleted=True)
        self.deal("Won", "4000", probability=100, closed_at=THIS_MONTH, is_deleted=True)

        response = self.forecast()

        self.assertEqual(response.data["open_pipeline"], "1000.00")
        self.assertEqual(response.data["open_deal_count"], 1)
        self.assertEqual(response.data["won_this_month"], "0.00")

    def test_weighted_sum_is_rounded_once_at_the_end(self):
        # 100.05 at 10% is 10.005 per deal. Rounding each deal would give
        # 10.01 + 10.01 = 20.02; the exact sum 20.01 is what must be returned.
        self.deal("New", "100.05", probability=10, name="r1")
        self.deal("New", "100.05", probability=10, name="r2")

        response = self.forecast()

        self.assertEqual(response.data["open_pipeline"], "200.10")
        self.assertEqual(response.data["weighted_forecast"], "20.01")

    def test_rounding_is_half_up(self):
        self.deal("New", "100.05", probability=10)

        response = self.forecast()

        self.assertEqual(response.data["weighted_forecast"], "10.01")


class DealForecastByStageTests(DealForecastBase):
    def test_by_stage_lists_the_open_stages_in_order_with_zero_rows(self):
        self.deal("Negotiation", "1000", probability=70)

        rows = self.forecast().data["by_stage"]

        self.assertEqual([r["stage"] for r in rows], OPEN_STAGES)
        self.assertEqual([r["count"] for r in rows], [0, 0, 1])
        self.assertEqual(rows[0]["total_amount"], "0.00")
        self.assertEqual(rows[0]["weighted_amount"], "0.00")
        self.assertEqual(rows[1]["total_amount"], "0.00")
        self.assertEqual(rows[2]["total_amount"], "1000.00")
        self.assertEqual(rows[2]["weighted_amount"], "700.00")

    def test_by_stage_never_contains_won_or_lost(self):
        self.deal("Won", "1000", probability=100, closed_at=THIS_MONTH)

        rows = self.forecast().data["by_stage"]

        self.assertEqual([r["stage"] for r in rows], OPEN_STAGES)


class DealForecastByMonthTests(DealForecastBase):
    def test_months_are_chronological_and_undated_deals_go_last_as_null(self):
        self.deal("New", "1000", probability=10, expected_close_date=date(2026, 12, 15))
        self.deal("New", "2000", probability=10)
        self.deal("Negotiation", "3000", probability=70,
                  expected_close_date=date(2026, 11, 30))
        self.deal("Negotiation", "500", probability=70,
                  expected_close_date=date(2026, 11, 1))
        self.deal("New", "400", probability=10, expected_close_date=date(2027, 1, 1))
        self.deal("New", "100", probability=10)

        response = self.forecast()
        rows = [dict(r) for r in response.data["by_month"]]

        self.assertEqual(
            rows,
            [
                {"month": "2026-11", "total_amount": "3500.00",
                 "weighted_amount": "2450.00"},
                {"month": "2026-12", "total_amount": "1000.00",
                 "weighted_amount": "100.00"},
                {"month": "2027-01", "total_amount": "400.00",
                 "weighted_amount": "40.00"},
                {"month": None, "total_amount": "2100.00",
                 "weighted_amount": "210.00"},
            ],
        )
        # Undated deals still count in the headline numbers.
        self.assertEqual(response.data["open_pipeline"], "7000.00")
        self.assertEqual(response.data["open_deal_count"], 6)

    def test_closed_deals_are_not_grouped_by_month(self):
        self.deal("Won", "5000", probability=100, closed_at=THIS_MONTH,
                  expected_close_date=date(2026, 11, 5))

        self.assertEqual(self.forecast().data["by_month"], [])

    def test_past_expected_close_dates_are_grouped_too(self):
        self.deal("New", "1000", probability=10, expected_close_date=date(2026, 1, 31))

        rows = self.forecast().data["by_month"]

        self.assertEqual([r["month"] for r in rows], ["2026-01"])


class DealForecastTimeZoneTests(DealForecastBase):
    def test_deal_closed_just_after_local_midnight_belongs_to_the_new_month(self):
        # 31 Oct 19:00 UTC = 1 Nov 00:30 in Kolkata, but still 31 Oct in UTC.
        self.deal("Won", "8000", probability=100,
                  closed_at=datetime(2026, 10, 31, 19, 0, tzinfo=dt_timezone.utc))

        kolkata = self.forecast(tz="Asia/Kolkata")
        utc = self.forecast(tz="UTC")

        self.assertEqual(kolkata.data["won_this_month"], "8000.00")
        self.assertEqual(utc.data["won_this_month"], "0.00")

    def test_deal_closed_just_after_local_month_end_belongs_to_the_next_month(self):
        # 30 Nov 19:00 UTC = 1 Dec 00:30 in Kolkata, but still 30 Nov in UTC.
        self.deal("Lost", "3000", probability=0, lost_reason="Price",
                  closed_at=datetime(2026, 11, 30, 19, 0, tzinfo=dt_timezone.utc))

        kolkata = self.forecast(tz="Asia/Kolkata")
        utc = self.forecast(tz="UTC")

        self.assertEqual(kolkata.data["lost_this_month"], "0.00")
        self.assertEqual(utc.data["lost_this_month"], "3000.00")

    def test_current_month_itself_depends_on_the_zone(self):
        # 31 Oct 20:00 UTC is already 1 Nov in Kolkata, still 31 Oct in UTC.
        now = datetime(2026, 10, 31, 20, 0, tzinfo=dt_timezone.utc)
        self.deal("Won", "6000", probability=100,
                  closed_at=datetime(2026, 10, 31, 10, 0, tzinfo=dt_timezone.utc))

        kolkata = self.forecast(now=now, tz="Asia/Kolkata")  # month = November
        utc = self.forecast(now=now, tz="UTC")                # month = October

        self.assertEqual(kolkata.data["won_this_month"], "0.00")
        self.assertEqual(utc.data["won_this_month"], "6000.00")

    def test_tz_defaults_to_the_project_time_zone(self):
        self.deal("Won", "8000", probability=100,
                  closed_at=datetime(2026, 10, 31, 19, 0, tzinfo=dt_timezone.utc))

        default = self.forecast()
        explicit = self.forecast(tz=settings.TIME_ZONE)

        self.assertEqual(default.status_code, status.HTTP_200_OK, default.data)
        self.assertEqual(default.data, explicit.data)

    def test_unknown_zone_is_a_400(self):
        response = self.forecast(tz="Not/AZone")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Unknown time zone 'Not/AZone'."})

    def test_month_bounds_in_december_roll_into_january(self):
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Kolkata")
        start, end = month_bounds(
            datetime(2026, 12, 20, 6, 0, tzinfo=dt_timezone.utc), tz,
        )

        self.assertEqual(start, datetime(2026, 12, 1, tzinfo=tz))
        self.assertEqual(end, datetime(2027, 1, 1, tzinfo=tz))

    def test_use_case_runs_with_an_injected_clock(self):
        self.deal("Won", "8000", probability=100, closed_at=THIS_MONTH)
        use_case = GetDealForecastUseCase(
            DjangoDealRepository(company_id=self.company.id)
        )

        result = use_case.execute(DealForecastQuery(timezone_name="UTC"), now=NOW)

        self.assertEqual(result.won_this_month, Decimal("8000.00"))
        with self.assertRaises(ValueError):
            use_case.execute(DealForecastQuery(timezone_name="Nope/Nope"), now=NOW)


class DealForecastOwnerFilterTests(DealForecastBase):
    def test_owner_id_limits_every_number(self):
        self.deal("New", "1000", probability=10, owner=self.admin,
                  expected_close_date=date(2026, 11, 30))
        self.deal("Negotiation", "4000", probability=70, owner=self.superadmin,
                  expected_close_date=date(2026, 12, 30))
        self.deal("Won", "900", probability=100, owner=self.admin,
                  closed_at=THIS_MONTH)
        self.deal("Won", "9000", probability=100, owner=self.superadmin,
                  closed_at=THIS_MONTH)

        response = self.forecast(owner_id=str(self.superadmin.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["open_pipeline"], "4000.00")
        self.assertEqual(response.data["weighted_forecast"], "2800.00")
        self.assertEqual(response.data["won_this_month"], "9000.00")
        self.assertEqual(response.data["open_deal_count"], 1)
        self.assertEqual([r["month"] for r in response.data["by_month"]], ["2026-12"])
        self.assertEqual([r["count"] for r in response.data["by_stage"]], [0, 0, 1])

    def test_invalid_owner_id_is_a_400(self):
        response = self.forecast(owner_id="nope")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {"detail"})


class DealForecastTenantIsolationTests(DealForecastBase):
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
        self.client_b = authenticated_client(self.superadmin_b)

        self.deal("New", "1000", probability=10)
        self.deal("Won", "400", probability=100, closed_at=THIS_MONTH)
        make_deal(self.company_b, self.admin_b, account=self.account_b, name="B open",
                  stage="Negotiation", amount=Decimal("90000"), probability=70)
        make_deal(self.company_b, self.admin_b, account=self.account_b, name="B won",
                  stage="Won", amount=Decimal("55000"), probability=100,
                  closed_at=THIS_MONTH)

    def test_each_company_only_sees_its_own_numbers(self):
        a = self.forecast()
        b = self.forecast(client=self.client_b)

        self.assertEqual(a.data["open_pipeline"], "1000.00")
        self.assertEqual(a.data["weighted_forecast"], "100.00")
        self.assertEqual(a.data["won_this_month"], "400.00")
        self.assertEqual(a.data["open_deal_count"], 1)

        self.assertEqual(b.data["open_pipeline"], "90000.00")
        self.assertEqual(b.data["weighted_forecast"], "63000.00")
        self.assertEqual(b.data["won_this_month"], "55000.00")
        self.assertEqual(b.data["open_deal_count"], 1)

    def test_owner_filter_cannot_reach_another_companys_deals(self):
        response = self.forecast(owner_id=str(self.admin_b.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["open_pipeline"], "0.00")
        self.assertEqual(response.data["won_this_month"], "0.00")
        self.assertEqual(response.data["open_deal_count"], 0)

    def test_anonymous_request_is_rejected(self):
        response = APIClient().get(FORECAST)

        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )
