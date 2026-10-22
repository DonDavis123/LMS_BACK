"""API tests for searching, filtering, sorting and paginating the Calls table.

Covers both list endpoints:
  * ``GET /api/calls/``          - one row per call
  * ``GET /api/calls/records/``  - one row per lead / contact (the Calls table)
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import status

from src.modules.calls.infrastructure.persistence.models import DjangoCallModel
from src.modules.calls.tests import (
    CallApiTestCase,
    _make_account,
    _make_contact,
    _make_lead,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    default_test_company,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User


def _filter(field, operator, value):
    return {"field": field, "operator": operator, "value": value}


class CallListQueryTestCase(CallApiTestCase):
    """Five calls across three records (lead, other lead, contact).

    ================  ============  ========  =====  ========  ==========
    record            owner         outcome   mins   type      notes
    ================  ============  ========  =====  ========  ==========
    Call Lead  (x2)   Call Owner    Connected 5/1    Outbound  pricing x2
    Other Lead        Zed Owner     Busy      0      Inbound   (none)
    Call Contact      Call Owner    Voicemail 10     Outbound  Renewal
    ================  ============  ========  =====  ========  ==========
    """

    def setUp(self):
        super().setUp()
        self.zed = User.objects.create_user(
            company=default_test_company(),
            email="zed@example.com",
            password="zed-password",
            name="Zed Owner",
            role=User.Role.ADMIN,
        )
        base = self.now - timedelta(days=10)

        self.lead_old = self._call(
            lead=self.lead, start=base, outcome="Connected", seconds=300,
            description="Asked about PRICING tiers",
        )
        self.lead_new = self._call(
            lead=self.lead, start=base + timedelta(days=3), outcome="Not Attended",
            seconds=60, description="Left a message",
        )
        self.other_lead_call = self._call(
            lead=self.other_lead, start=base + timedelta(days=1), outcome="Busy",
            seconds=0, owner=self.zed, call_type="Inbound", description=None,
        )
        self.contact_call = self._call(
            contact=self.contact, account=self.account,
            start=base + timedelta(days=2), outcome="Voicemail", seconds=600,
            description="Contract renewal reminder",
        )

    # ---------- helpers ----------

    def _call(
        self,
        *,
        start,
        outcome,
        seconds,
        lead=None,
        contact=None,
        account=None,
        owner=None,
        call_type="Outbound",
        description=None,
    ):
        owner = owner or self.user
        return DjangoCallModel.objects.create(
            company=default_test_company(),
            lead=lead,
            contact=contact,
            account=account,
            owner=owner,
            created_by=owner,
            call_type=call_type,
            outcome=outcome,
            call_start_time=start,
            duration_seconds=seconds,
            description=description,
        )

    def _records(self, **params):
        query = {k: v for k, v in params.items() if v is not None}
        if "filters" in query and not isinstance(query["filters"], str):
            query["filters"] = json.dumps(query["filters"])
        return self.client.get("/api/calls/records/", query)

    def _record_names(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [row["record_name"] for row in response.data["results"]]

    def _call_ids(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return [row["id"] for row in response.data["results"]]


class CallSearchTests(CallListQueryTestCase):
    def test_search_by_lead_or_contact_name_is_partial_and_case_insensitive(self):
        self.assertEqual(self._record_names(self._records(search="call lead")), ["Call Lead"])
        self.assertEqual(self._record_names(self._records(search="CONTACT")), ["Call Contact"])
        # "lead" is in both lead names but in neither contact name.
        self.assertCountEqual(
            self._record_names(self._records(search="lead")),
            ["Call Lead", "Other Lead"],
        )

    def test_search_by_account_name(self):
        self.assertEqual(
            self._record_names(self._records(search="Call Account")),
            ["Call Contact"],
        )

    def test_search_by_owner_name(self):
        self.assertEqual(self._record_names(self._records(search="zed")), ["Other Lead"])

    def test_search_by_notes(self):
        self.assertEqual(self._record_names(self._records(search="renewal")), ["Call Contact"])

    def test_search_with_no_match_returns_an_empty_page(self):
        response = self._records(search="nothing-matches-this")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["pagination"]["total"], 0)
        self.assertEqual(response.data["pagination"]["total_pages"], 0)

    def test_blank_search_is_ignored(self):
        self.assertEqual(len(self._records(search="   ").data["results"]), 3)

    def test_wildcard_characters_are_matched_literally(self):
        self.assertEqual(self._record_names(self._records(search="%")), [])
        self.assertEqual(self._record_names(self._records(search="_")), [])

    def test_search_longer_than_the_limit_is_rejected(self):
        response = self._records(search="x" * 101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_narrows_the_calls_a_record_is_summarised_from(self):
        # Only the older call on "Call Lead" mentions pricing, so that call is
        # the one shown and the record counts just the matching call.
        response = self._records(search="pricing")

        self.assertEqual(response.data["pagination"]["total"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["record_name"], "Call Lead")
        self.assertEqual(row["call_count"], 1)
        self.assertEqual(row["latest_call"]["id"], str(self.lead_old.id))

    def test_search_that_matches_every_call_keeps_the_full_count(self):
        row = self._records(search="call lead").data["results"][0]

        self.assertEqual(row["call_count"], 2)
        self.assertEqual(row["latest_call"]["id"], str(self.lead_new.id))

    def test_search_combines_with_filters(self):
        response = self._records(
            search="lead",
            filters=[_filter("outcome", "equals", "Busy")],
        )

        self.assertEqual(self._record_names(response), ["Other Lead"])

    def test_search_applies_to_the_flat_call_list_too(self):
        response = self._list(search="call lead", sort_by="call_start_time", sort_direction="asc")

        self.assertEqual(
            self._call_ids(response),
            [str(self.lead_old.id), str(self.lead_new.id)],
        )

    def test_search_never_leaks_another_companys_calls(self):
        company_b = make_company("Search Co B")
        admin_b = make_user(company_b, User.Role.ADMIN, name="Call Owner B")
        lead_b = _make_lead(company_b, admin_b, "Call Lead B")
        DjangoCallModel.objects.create(
            company=company_b,
            lead=lead_b,
            owner=admin_b,
            created_by=admin_b,
            outcome="Connected",
            call_start_time=self.now - timedelta(hours=1),
            description="pricing",
        )

        mine = self._records(search="pricing")
        self.assertEqual(self._record_names(mine), ["Call Lead"])

        theirs = authenticated_client(admin_b).get("/api/calls/records/", {"search": "call lead"})
        self.assertEqual([r["record_name"] for r in theirs.data["results"]], ["Call Lead B"])


class CallFilterTests(CallListQueryTestCase):
    def test_filter_by_related_record_name(self):
        cases = [
            ("contains", "other", ["Other Lead"]),
            ("equals", "call contact", ["Call Contact"]),
            ("starts_with", "Call", ["Call Contact", "Call Lead"]),
            ("ends_with", "Lead", ["Call Lead", "Other Lead"]),
            ("not_contains", "lead", ["Call Contact"]),
            ("not_equals", "Call Lead", ["Call Contact", "Other Lead"]),
        ]
        for operator, value, expected in cases:
            with self.subTest(operator=operator):
                response = self._records(filters=[_filter("record_name", operator, value)])
                self.assertCountEqual(self._record_names(response), expected)

    def test_filter_by_account_name(self):
        response = self._records(filters=[_filter("account_name", "contains", "account")])
        self.assertEqual(self._record_names(response), ["Call Contact"])

        # Calls without an account are kept by the negative operators.
        response = self._records(filters=[_filter("account_name", "not_contains", "account")])
        self.assertCountEqual(self._record_names(response), ["Call Lead", "Other Lead"])

    def test_filter_by_record_type(self):
        cases = [
            ("equals", "LEAD", ["Call Lead", "Other Lead"]),
            ("equals", "CONTACT", ["Call Contact"]),
            ("not_equals", "LEAD", ["Call Contact"]),
            ("in", ["LEAD", "CONTACT"], ["Call Lead", "Other Lead", "Call Contact"]),
            ("not_in", ["CONTACT"], ["Call Lead", "Other Lead"]),
        ]
        for operator, value, expected in cases:
            with self.subTest(operator=operator, value=value):
                response = self._records(filters=[_filter("record_type", operator, value)])
                self.assertCountEqual(self._record_names(response), expected)

    def test_invalid_record_type_filters_are_rejected(self):
        for operator, value in (("equals", "ACCOUNT"), ("in", []), ("in", ["LEAD", "X"]), ("contains", "LEAD")):
            with self.subTest(operator=operator, value=value):
                response = self._records(filters=[_filter("record_type", operator, value)])
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_duration(self):
        cases = [
            ("after", 300, {"Call Lead", "Call Contact"}),   # at least 5 minutes
            ("before", 60, {"Call Lead", "Other Lead"}),      # at most 1 minute
            ("equals", 0, {"Other Lead"}),
            ("not_equals", 0, {"Call Lead", "Call Contact"}),
            ("in", [60, 600], {"Call Lead", "Call Contact"}),
        ]
        for operator, value, expected in cases:
            with self.subTest(operator=operator, value=value):
                response = self._records(filters=[_filter("duration_seconds", operator, value)])
                self.assertEqual(set(self._record_names(response)), expected)

    def test_non_numeric_duration_is_rejected(self):
        for value in ("abc", True, None):
            with self.subTest(value=value):
                response = self._records(filters=[_filter("duration_seconds", "equals", value)])
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_outcome_type_and_owner(self):
        self.assertEqual(
            self._record_names(self._records(filters=[_filter("outcome", "in", ["Busy", "Voicemail"])])),
            ["Call Contact", "Other Lead"],
        )
        self.assertEqual(
            self._record_names(self._records(filters=[_filter("call_type", "equals", "Inbound")])),
            ["Other Lead"],
        )
        self.assertEqual(
            self._record_names(self._records(filters=[_filter("owner", "equals", str(self.zed.id))])),
            ["Other Lead"],
        )

    def test_filter_by_notes(self):
        response = self._records(filters=[_filter("description", "contains", "pricing")])
        self.assertEqual(self._record_names(response), ["Call Lead"])

        # A call without notes is not "contains" anything but is "doesn't contain".
        response = self._records(filters=[_filter("description", "not_contains", "pricing")])
        self.assertCountEqual(self._record_names(response), ["Call Lead", "Other Lead", "Call Contact"])

    def test_multiple_filters_are_anded(self):
        response = self._records(
            filters=[
                _filter("record_type", "equals", "LEAD"),
                _filter("duration_seconds", "after", 1),
            ]
        )
        self.assertEqual(self._record_names(response), ["Call Lead"])

    def test_filtered_record_is_summarised_from_matching_calls_only(self):
        response = self._records(filters=[_filter("outcome", "equals", "Connected")])

        row = response.data["results"][0]
        self.assertEqual(row["call_count"], 1)
        self.assertEqual(row["latest_call"]["id"], str(self.lead_old.id))

    def test_unsupported_field_and_operator_are_rejected(self):
        for condition in (
            _filter("nope", "equals", "x"),
            _filter("record_name", "after", "x"),
            _filter("outcome", "contains", "Busy"),
        ):
            with self.subTest(condition=condition):
                response = self._records(filters=[condition])
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CallDateFilterTests(CallListQueryTestCase):
    """Date-only values are whole calendar days in the project time zone."""

    def setUp(self):
        super().setUp()
        tz = ZoneInfo("Asia/Kolkata")
        # Two calls on the SAME calendar day (2030-01-15): early morning and late night.
        self.early = self._call(
            lead=self.lead, outcome="Connected", seconds=10,
            start=datetime(2030, 1, 15, 0, 30, tzinfo=tz),
        )
        self.late = self._call(
            lead=self.other_lead, outcome="Connected", seconds=10, owner=self.zed,
            start=datetime(2030, 1, 15, 23, 45, tzinfo=tz),
        )
        self.next_day = self._call(
            contact=self.other_contact, outcome="Connected", seconds=10,
            start=datetime(2030, 1, 16, 0, 5, tzinfo=tz),
        )

    def _on(self, operator, value):
        response = self._list(
            sort_by="call_start_time", sort_direction="asc",
            filters=json.dumps([_filter("call_start_time", operator, value)]),
        )
        return self._call_ids(response)

    def test_equals_a_day_matches_the_whole_day(self):
        self.assertEqual(
            self._on("equals", "2030-01-15"),
            [str(self.early.id), str(self.late.id)],
        )

    def test_between_includes_every_call_on_the_last_day(self):
        self.assertEqual(
            self._on("between", {"from": "2030-01-15", "to": "2030-01-15"}),
            [str(self.early.id), str(self.late.id)],
        )
        self.assertEqual(
            self._on("between", {"from": "2030-01-15", "to": "2030-01-16"}),
            [str(self.early.id), str(self.late.id), str(self.next_day.id)],
        )

    def test_before_and_after_a_day_are_inclusive(self):
        self.assertEqual(
            self._on("after", "2030-01-16"),
            [str(self.next_day.id)],
        )
        self.assertEqual(
            self._on("before", "2030-01-15")[-2:],
            [str(self.early.id), str(self.late.id)],
        )

    def test_exact_datetimes_are_exact_instants(self):
        exact = self.early.call_start_time.isoformat()
        self.assertEqual(self._on("equals", exact), [str(self.early.id)])

    def test_reversed_or_invalid_ranges_are_rejected(self):
        for value in (
            {"from": "2030-01-16", "to": "2030-01-15"},
            {"from": "2030-01-15"},
            {"from": "not-a-date", "to": "2030-01-15"},
        ):
            with self.subTest(value=value):
                response = self._list(
                    filters=json.dumps([_filter("call_start_time", "between", value)]),
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CallSortTests(CallListQueryTestCase):
    def test_sort_by_related_record_name_ignores_case(self):
        # An all-lowercase lead name must still sort alphabetically, not last.
        lowercase = _make_lead(default_test_company(), self.user, "apple lead")
        self._call(lead=lowercase, outcome="Busy", seconds=1, start=self.now - timedelta(days=1))

        asc = self._record_names(self._records(sort_by="record_name", sort_direction="asc"))
        desc = self._record_names(self._records(sort_by="record_name", sort_direction="desc"))

        self.assertEqual(asc, ["apple lead", "Call Contact", "Call Lead", "Other Lead"])
        self.assertEqual(desc, list(reversed(asc)))

    def test_sort_by_owner_name(self):
        asc = self._record_names(self._records(sort_by="owner", sort_direction="asc"))

        # "Call Owner" < "Zed Owner"
        self.assertEqual(asc[-1], "Other Lead")
        self.assertEqual(
            self._record_names(self._records(sort_by="owner", sort_direction="desc"))[0],
            "Other Lead",
        )

    def test_sort_by_the_columns_of_the_latest_call(self):
        cases = [
            ("duration_seconds", "desc", ["Call Contact", "Call Lead", "Other Lead"]),
            ("duration_seconds", "asc", ["Other Lead", "Call Lead", "Call Contact"]),
            ("outcome", "asc", ["Other Lead", "Call Lead", "Call Contact"]),
            ("call_start_time", "desc", ["Call Lead", "Call Contact", "Other Lead"]),
            ("call_count", "desc", ["Call Lead"]),
        ]
        for field, direction, expected in cases:
            with self.subTest(field=field, direction=direction):
                names = self._record_names(self._records(sort_by=field, sort_direction=direction))
                self.assertEqual(names[: len(expected)], expected)

    def test_sort_by_notes_puts_calls_without_notes_last(self):
        for direction in ("asc", "desc"):
            with self.subTest(direction=direction):
                names = self._record_names(
                    self._records(sort_by="description", sort_direction=direction),
                )
                self.assertEqual(names[-1], "Other Lead")

    def test_sort_applies_to_the_flat_call_list(self):
        by_name = self._call_ids(self._list(sort_by="record_name", sort_direction="asc"))
        self.assertEqual(by_name[0], str(self.contact_call.id))          # Call Contact
        self.assertEqual(by_name[-1], str(self.other_lead_call.id))      # Other Lead

        by_owner = self._call_ids(self._list(sort_by="owner", sort_direction="desc"))
        self.assertEqual(by_owner[0], str(self.other_lead_call.id))      # Zed Owner

    def test_unsortable_field_is_rejected(self):
        for url in ("/api/calls/", "/api/calls/records/"):
            with self.subTest(url=url):
                response = self.client.get(url, {"sort_by": "lead_id"})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        bad_direction = self._records(sort_by="outcome", sort_direction="sideways")
        self.assertEqual(bad_direction.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_order_is_still_the_most_recently_updated_record(self):
        # Touch the contact call so its record becomes the most recently updated.
        DjangoCallModel.objects.filter(id=self.contact_call.id).update(updated_at=timezone.now())

        self.assertEqual(self._record_names(self._records())[0], "Call Contact")


class CallPaginationWithQueryTests(CallListQueryTestCase):
    def setUp(self):
        super().setUp()
        base = self.now - timedelta(days=30)
        for index in range(12):
            lead = _make_lead(default_test_company(), self.user, f"Bulk Lead {index:02d}")
            self._call(
                lead=lead, outcome="Connected", seconds=index,
                start=base + timedelta(hours=index), description="bulk",
            )

    def test_pages_are_disjoint_complete_and_sorted(self):
        names = []
        for page in (1, 2, 3):
            response = self._records(
                search="bulk lead", sort_by="record_name", sort_direction="asc",
                page=page, page_size=5,
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(
                response.data["pagination"],
                {"page": page, "page_size": 5, "total": 12, "total_pages": 3},
            )
            names.extend(self._record_names(response))

        self.assertEqual(names, [f"Bulk Lead {i:02d}" for i in range(12)])

    def test_pagination_total_reflects_filters(self):
        response = self._records(
            filters=[_filter("duration_seconds", "after", 8)],
            page=1, page_size=10,
        )

        # Bulk leads 08..11 have >= 8 seconds, plus Call Lead (300s latest-matching
        # call) and Call Contact (600s). Other Lead has 0s.
        self.assertEqual(response.data["pagination"]["total"], 6)

    def test_page_past_the_end_is_empty_not_an_error(self):
        response = self._records(search="bulk", page=9, page_size=10)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["pagination"]["total"], 12)

    def test_page_size_above_the_cap_is_rejected(self):
        self.assertEqual(self._records(page_size=51).status_code, status.HTTP_400_BAD_REQUEST)
