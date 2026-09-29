import json
from datetime import datetime, timedelta

from django.utils import timezone
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
from src.modules.users.infrastructure.persistence.models import User


class LeadListFilterApiTests(APITestCase):
    """
    End-to-end: HTTP query -> view -> parse_list_query -> use case ->
    repository -> PostgreSQL -> paginated response.
    """

    URL = "/api/leads/"

    def setUp(self):
        self.user = User.objects.create_user(
            email="filter-owner@example.com",
            password="filter-password",
            name="Filter Owner",
            role=User.Role.ADMIN,
        )
        self.client.force_authenticate(self.user)
        now = timezone.now()

        def account(name, **extra):
            return DjangoAccountModel.objects.create(
                account_owner=self.user, account_name=name,
                created_by=self.user, created_at=now,
                modified_by=self.user, updated_at=now, **extra,
            )

        def contact(name, **extra):
            return DjangoContactModel.objects.create(
                contact_owner=self.user, name=name,
                created_by=self.user, created_at=now,
                modified_by=self.user, updated_at=now, **extra,
            )

        def lead(name, **extra):
            return DjangoLeadModel.objects.create(name=name, owner=self.user, **extra)

        self.abc_account = account("ABC Industries")
        self.deleted_account = account("Ghost Corp", is_deleted=True)
        account("Zeta Holdings")

        contact("John Smith", email="john@abc.example")
        contact("Deleted Dan", email="dan@ghost.example", is_deleted=True)
        contact("Mary Jones", mobile="8888800000")

        # Case 1: account matches + contact matches (by name)
        self.rahul = lead(
            "John Smith", company_name="abc industries",
            lead_status="Contacted", city="Kochi", email="js@lead.example",
        )
        # Case 2: account matches, no contact
        self.acct_only = lead(
            "Rahul Nair", company_name="ABC Industries", lead_status="Not Contacted",
        )
        # Case 3: no account (company blank), contact matches (by email)
        self.contact_only = lead(
            "Johnny S", company_name=None, email="JOHN@abc.example", lead_status="Contacted",
        )
        # Case 4: neither account nor contact
        self.neither = lead("Nobody Special", company_name="Unknown Ltd")
        # Contact matched via mobile number
        self.by_mobile = lead("Mary J", mobile_number="8888800000", company_name="")
        # Only matches a soft-deleted account / contact
        self.ghost = lead(
            "Dan Ghost", company_name="Ghost Corp", email="dan@ghost.example",
        )
        # Converted / deleted leads must never be listed
        lead("Converted Rahul", company_name="ABC Industries", is_converted=True)
        lead("Deleted Rahul", company_name="ABC Industries", is_deleted=True)

        # Park every lead far in the past so date tests control what matches.
        parked = timezone.make_aware(datetime(2020, 1, 1, 12, 0, 0))
        DjangoLeadModel.objects.update(created_at=parked, updated_at=parked)

    # ------------------------------------------------------------ helpers
    def _get(self, filters=None, **params):
        query = dict(params)
        if filters is not None:
            query["filters"] = json.dumps(filters)
        return self.client.get(self.URL, query)

    def _names(self, filters=None, **params):
        response = self._get(filters, **params)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return sorted(item["name"] for item in response.data["results"])

    @staticmethod
    def _f(field, operator, value):
        return {"field": field, "operator": operator, "value": value}

    # --------------------------------------------------------- lead name
    def test_lead_name_partial_case_insensitive(self):
        self.assertEqual(self._names([self._f("name", "contains", "RAHUL")]), ["Rahul Nair"])

    def test_lead_name_exact_and_nonexistent(self):
        self.assertEqual(self._names([self._f("name", "equals", "nobody special")]), ["Nobody Special"])
        self.assertEqual(self._names([self._f("name", "contains", "zzz-none")]), [])

    # ------------------------------------------------------ account name
    def test_account_name_existing_and_partial(self):
        expected = ["John Smith", "Rahul Nair"]
        self.assertEqual(self._names([self._f("account_name", "equals", "ABC Industries")]), expected)
        self.assertEqual(self._names([self._f("account_name", "contains", "abc")]), expected)
        self.assertEqual(self._names([self._f("account_name", "starts_with", "ab")]), expected)

    def test_account_name_nonexistent(self):
        self.assertEqual(self._names([self._f("account_name", "contains", "nothing")]), [])

    def test_account_name_ignores_soft_deleted_accounts(self):
        self.assertEqual(self._names([self._f("account_name", "contains", "Ghost")]), [])

    def test_account_name_negative_operator_keeps_leads_without_account(self):
        names = self._names([self._f("account_name", "not_contains", "ABC")])
        self.assertIn("Nobody Special", names)      # company has no Account
        self.assertIn("Johnny S", names)            # no company at all
        self.assertNotIn("Rahul Nair", names)
        self.assertNotIn("John Smith", names)

    # ------------------------------------------------------ contact name
    def test_contact_name_matches_by_name_email_and_mobile(self):
        self.assertEqual(
            self._names([self._f("contact_name", "contains", "john")]),
            ["John Smith", "Johnny S"],
        )
        self.assertEqual(self._names([self._f("contact_name", "equals", "Mary Jones")]), ["Mary J"])

    def test_contact_name_nonexistent_and_soft_deleted(self):
        self.assertEqual(self._names([self._f("contact_name", "contains", "nobody-here")]), [])
        self.assertEqual(self._names([self._f("contact_name", "contains", "Deleted Dan")]), [])

    def test_blank_lead_values_never_match_blank_contact_values(self):
        DjangoContactModel.objects.filter(name="Mary Jones").update(email="", phone="")
        DjangoLeadModel.objects.filter(pk=self.neither.pk).update(email="", phone="")
        self.assertNotIn("Nobody Special", self._names([self._f("contact_name", "contains", "Mary")]))

    def test_invalid_related_operator_returns_400(self):
        response = self._get([self._f("account_name", "between", "x")])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_empty_related_value_returns_400(self):
        response = self._get([self._f("contact_name", "contains", "")])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------- combined filters
    def test_combined_filters_are_anded(self):
        self.assertEqual(
            self._names([
                self._f("name", "contains", "john"),
                self._f("account_name", "contains", "abc"),
                self._f("contact_name", "contains", "smith"),
                self._f("lead_status", "equals", "Contacted"),
            ]),
            ["John Smith"],
        )
        self.assertEqual(
            self._names([
                self._f("account_name", "contains", "abc"),
                self._f("lead_status", "equals", "Not Contacted"),
            ]),
            ["Rahul Nair"],
        )
        self.assertEqual(
            self._names([
                self._f("account_name", "contains", "abc"),
                self._f("contact_name", "contains", "john"),
            ]),
            ["John Smith"],
        )
        self.assertEqual(
            self._names([
                self._f("contact_name", "contains", "john"),
                self._f("city", "equals", "Kochi"),
            ]),
            ["John Smith"],
        )

    def test_combined_filters_with_no_common_match(self):
        self.assertEqual(
            self._names([
                self._f("name", "contains", "rahul"),
                self._f("contact_name", "contains", "john"),
            ]),
            [],
        )

    # -------------------------------------------------------- pagination
    def test_pagination_total_reflects_filtered_dataset(self):
        for index in range(25):
            DjangoLeadModel.objects.create(
                name=f"Bulk {index:02d}", company_name="ABC Industries", owner=self.user,
            )
        filters = [self._f("account_name", "equals", "ABC Industries")]

        page_one = self._get(filters, page=1, page_size=10)
        self.assertEqual(page_one.status_code, status.HTTP_200_OK)
        self.assertEqual(len(page_one.data["results"]), 10)
        # 25 bulk + Rahul Nair + John Smith; converted/deleted leads excluded.
        self.assertEqual(page_one.data["pagination"]["total"], 27)
        self.assertEqual(page_one.data["pagination"]["total_pages"], 3)

        page_three = self._get(filters, page=3, page_size=10)
        self.assertEqual(len(page_three.data["results"]), 7)

    # -------------------------------------------------------------- dates
    def _set_created(self, lead, moment):
        DjangoLeadModel.objects.filter(pk=lead.pk).update(created_at=moment)

    def _aware(self, year, month, day, hour=0, minute=0, second=0):
        return timezone.make_aware(datetime(year, month, day, hour, minute, second))

    def test_date_range_is_inclusive_of_last_day(self):
        self._set_created(self.rahul, self._aware(2026, 9, 1, 0, 0, 0))
        self._set_created(self.acct_only, self._aware(2026, 9, 30, 23, 59, 59))
        self._set_created(self.contact_only, self._aware(2026, 10, 1, 0, 0, 0))
        self._set_created(self.neither, self._aware(2026, 8, 31, 23, 59, 59))

        names = self._names([
            self._f("created_at", "between", {"from": "2026-09-01", "to": "2026-09-30"}),
        ])
        self.assertEqual(names, ["John Smith", "Rahul Nair"])

    def test_same_start_and_end_date_returns_that_whole_day(self):
        self._set_created(self.rahul, self._aware(2026, 9, 15, 0, 0, 0))
        self._set_created(self.acct_only, self._aware(2026, 9, 15, 23, 59, 59))
        self._set_created(self.neither, self._aware(2026, 9, 16, 0, 0, 0))

        between = self._names([
            self._f("created_at", "between", {"from": "2026-09-15", "to": "2026-09-15"}),
        ])
        self.assertEqual(between, ["John Smith", "Rahul Nair"])
        equals = self._names([self._f("created_at", "equals", "2026-09-15")])
        self.assertEqual(equals, ["John Smith", "Rahul Nair"])

    def test_from_only_and_to_only(self):
        self._set_created(self.rahul, self._aware(2026, 9, 10, 12))
        self._set_created(self.acct_only, self._aware(2026, 9, 20, 12))
        for other in (self.contact_only, self.neither, self.by_mobile, self.ghost):
            self._set_created(other, self._aware(2020, 1, 1))

        after = self._names([self._f("created_at", "after", "2026-09-20")])
        self.assertEqual(after, ["Rahul Nair"])
        before = self._names([self._f("created_at", "before", "2026-09-10")])
        self.assertIn("John Smith", before)         # on/before includes the day itself
        self.assertNotIn("Rahul Nair", before)

    def test_full_iso_datetime_is_exact_instant(self):
        self._set_created(self.rahul, self._aware(2026, 9, 15, 10, 0, 0))
        self._set_created(self.acct_only, self._aware(2026, 9, 15, 18, 0, 0))
        for other in (self.contact_only, self.neither, self.by_mobile, self.ghost):
            self._set_created(other, self._aware(2020, 1, 1))
        cutoff = self._aware(2026, 9, 15, 12, 0, 0).isoformat()
        self.assertEqual(self._names([self._f("created_at", "after", cutoff)]), ["Rahul Nair"])

    def test_ui_emitted_day_boundaries_round_trip(self):
        """Payload shape produced by the FilterBar for an IST user: 1 Sep - 30 Sep."""
        self._set_created(self.rahul, self._aware(2026, 9, 1, 0, 0, 0))            # first instant
        self._set_created(self.acct_only, self._aware(2026, 9, 30, 23, 59, 59))    # last second
        self._set_created(self.contact_only, self._aware(2026, 10, 1, 0, 0, 0))    # just outside
        self._set_created(self.neither, self._aware(2026, 8, 31, 23, 59, 59))      # just outside
        ist_range = {"from": "2026-08-31T18:30:00.000Z", "to": "2026-09-30T18:29:59.999Z"}
        self.assertEqual(
            self._names([self._f("created_at", "between", ist_range)]),
            ["John Smith", "Rahul Nair"],
        )
        self.assertEqual(
            self._names([self._f("created_at", "before", "2026-09-30T18:29:59.999Z")]),
            sorted(n for n in ["John Smith", "Rahul Nair", "Nobody Special", "Mary J", "Dan Ghost"]),
        )

    def test_updated_at_filter(self):
        DjangoLeadModel.objects.filter(pk=self.rahul.pk).update(
            updated_at=self._aware(2026, 9, 5, 9)
        )
        DjangoLeadModel.objects.exclude(pk=self.rahul.pk).update(updated_at=self._aware(2020, 1, 1))
        self.assertEqual(
            self._names([self._f("updated_at", "between", {"from": "2026-09-05", "to": "2026-09-05"})]),
            ["John Smith"],
        )

    def test_invalid_date_and_reversed_range_return_400(self):
        bad = self._get([self._f("created_at", "after", "not-a-date")])
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        reversed_range = self._get([
            self._f("created_at", "between", {"from": "2026-09-30", "to": "2026-09-01"}),
        ])
        self.assertEqual(reversed_range.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_filters_returns_all_active_leads(self):
        self.assertEqual(len(self._names()), 6)

    def test_clearing_filters_restores_full_list(self):
        filtered = self._names([self._f("account_name", "contains", "abc")])
        cleared = self._names([])
        self.assertLess(len(filtered), len(cleared))
        self.assertEqual(len(cleared), 6)

    def test_mobile_number_filter(self):
        self.assertEqual(self._names([self._f("mobile_number", "contains", "88888")]), ["Mary J"])

    def test_queries_do_not_scale_with_result_count(self):
        for index in range(15):
            DjangoLeadModel.objects.create(
                name=f"Perf {index}", company_name="ABC Industries", owner=self.user,
            )
        filters = [
            self._f("account_name", "contains", "abc"),
            self._f("contact_name", "contains", "john"),
        ]
        with self.assertNumQueries(_QUERY_BUDGET):
            self._get(filters, page_size=50)


# count + page fetch (+ auth lookups already forced by force_authenticate = 0)
_QUERY_BUDGET = 2
