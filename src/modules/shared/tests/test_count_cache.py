"""Tests for the version-keyed list-total cache (``count_cache``).

The cache is always off in tests (``COUNT_CACHE_TTL_SECONDS = 0``), so every
test here switches it on with ``override_settings``.
"""

import json
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.application.dto.list_query import FilterCondition
from src.modules.shared.infrastructure.caching import count_cache
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

ENABLED = override_settings(COUNT_CACHE_TTL_SECONDS=600)


class FilterHashTests(SimpleTestCase):
    def parts(self, search=None, filters=(), **extra):
        return count_cache.build_filter_parts(search, filters, **extra)

    def test_filter_order_and_list_order_do_not_matter(self):
        a = FilterCondition("lead_status", "in", ["A", "B"])
        b = FilterCondition("city", "equals", "Kochi")
        first = count_cache.filter_hash(self.parts(filters=(a, b)))
        second = count_cache.filter_hash(
            self.parts(filters=(b, FilterCondition("lead_status", "in", ["B", "A"])))
        )
        self.assertEqual(first, second)

    def test_every_part_changes_the_hash(self):
        base = count_cache.filter_hash(self.parts("x", is_deleted=False))
        variants = [
            self.parts("y", is_deleted=False),
            self.parts("x", is_deleted=True),
            self.parts("x", is_deleted=False, is_converted=False),
            self.parts("x", (FilterCondition("city", "equals", "A"),), is_deleted=False),
            self.parts("x", is_deleted=False, variant="records"),
        ]
        hashes = {count_cache.filter_hash(v) for v in variants}
        self.assertNotIn(base, hashes)
        self.assertEqual(len(hashes), len(variants))

    def test_no_search_and_blank_search_are_the_same(self):
        self.assertEqual(
            count_cache.filter_hash(self.parts(None)),
            count_cache.filter_hash(self.parts("  ")),
        )


@ENABLED
class GetOrCountTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.parts = count_cache.build_filter_parts("x", (), is_deleted=False)

    def test_second_call_uses_the_cache(self):
        fn = mock.Mock(return_value=7)
        self.assertEqual(count_cache.get_or_count("c1", "leads", self.parts, fn), 7)
        self.assertEqual(count_cache.get_or_count("c1", "leads", self.parts, fn), 7)
        self.assertEqual(fn.call_count, 1)

    def test_bump_makes_the_old_total_unreachable(self):
        fn = mock.Mock(side_effect=[7, 8])
        count_cache.get_or_count("c1", "leads", self.parts, fn)
        count_cache.bump_version("c1", "leads")
        self.assertEqual(count_cache.get_or_count("c1", "leads", self.parts, fn), 8)

    def test_other_company_and_other_resource_never_share_a_key(self):
        count_cache.get_or_count("c1", "leads", self.parts, lambda: 1)
        self.assertEqual(count_cache.get_or_count("c2", "leads", self.parts, lambda: 2), 2)
        self.assertEqual(count_cache.get_or_count("c1", "tasks", self.parts, lambda: 3), 3)
        # A bump for one company leaves the other company's entry alone.
        count_cache.bump_version("c1", "leads")
        self.assertEqual(count_cache.get_or_count("c2", "leads", self.parts, lambda: 99), 2)

    def test_different_filter_does_not_reuse_a_key(self):
        other = count_cache.build_filter_parts(
            "x", (FilterCondition("city", "equals", "Kochi"),), is_deleted=False
        )
        count_cache.get_or_count("c1", "leads", self.parts, lambda: 1)
        self.assertEqual(count_cache.get_or_count("c1", "leads", other, lambda: 5), 5)

    def test_cache_read_failure_falls_back_to_the_count(self):
        with mock.patch.object(count_cache.cache, "get", side_effect=RuntimeError("down")):
            self.assertEqual(
                count_cache.get_or_count("c1", "leads", self.parts, lambda: 4), 4
            )

    def test_cache_write_failure_still_returns_the_count(self):
        with mock.patch.object(count_cache.cache, "set", side_effect=RuntimeError("down")):
            self.assertEqual(
                count_cache.get_or_count("c1", "leads", self.parts, lambda: 4), 4
            )

    def test_bump_failure_never_raises(self):
        with mock.patch.object(count_cache.cache, "incr", side_effect=RuntimeError("down")):
            count_cache.bump_version("c1", "leads")

    def test_count_errors_are_not_swallowed(self):
        with self.assertRaises(ZeroDivisionError):
            count_cache.get_or_count("c1", "leads", self.parts, lambda: 1 / 0)

    def test_disabled_cache_always_counts(self):
        fn = mock.Mock(return_value=3)
        with override_settings(COUNT_CACHE_TTL_SECONDS=0):
            count_cache.get_or_count("c1", "leads", self.parts, fn)
            count_cache.get_or_count("c1", "leads", self.parts, fn)
        self.assertEqual(fn.call_count, 2)


@ENABLED
class LeadListTotalCacheTests(APITestCase):
    URL = "/api/leads/"

    def setUp(self):
        cache.clear()
        self.company = make_company("Cache A", "cache-a")
        self.other_company = make_company("Cache B", "cache-b")
        self.admin = make_user(self.company, User.Role.ADMIN, "cache-a@example.com")
        self.other_admin = make_user(
            self.other_company, User.Role.ADMIN, "cache-b@example.com"
        )
        self.client = authenticated_client(self.admin)
        self.other_client = authenticated_client(self.other_admin)

    def lead(self, name, company=None, owner=None, **extra):
        return DjangoLeadModel.objects.create(
            company=company or self.company,
            owner=owner or self.admin,
            name=name,
            **extra,
        )

    def total(self, client=None, filters=None):
        params = {"filters": json.dumps(filters)} if filters else {}
        response = (client or self.client).get(self.URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.data["pagination"]["total"]

    def count_queries(self, call):
        table = DjangoLeadModel._meta.db_table
        with CaptureQueriesContext(connection) as ctx:
            call()
        return [
            q["sql"] for q in ctx.captured_queries
            if "COUNT(" in q["sql"].upper() and table in q["sql"]
        ]

    def test_second_identical_request_does_not_run_count(self):
        self.lead("One")
        self.assertEqual(len(self.count_queries(self.total)), 1)
        self.assertEqual(self.count_queries(self.total), [])

    def test_paging_and_sorting_share_the_cached_total(self):
        self.lead("One")
        self.total()
        queries = self.count_queries(
            lambda: self.client.get(
                self.URL, {"page": 1, "page_size": 5, "sort_by": "name"}
            )
        )
        self.assertEqual(queries, [])

    def test_create_delete_and_convert_change_the_total_at_once(self):
        self.assertEqual(self.total(), 0)

        first = self.lead("First")
        self.assertEqual(self.total(), 1)
        self.lead("Second")
        self.assertEqual(self.total(), 2)

        response = self.client.delete(f"{self.URL}{first.id}/delete/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.total(), 1)

        remaining = DjangoLeadModel.objects.get(name="Second", company=self.company)
        response = self.client.post(
            f"{self.URL}{remaining.id}/convert/",
            {"account_action": "create_new", "contact_action": "create_new"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.total(), 0)

    def test_queryset_update_with_explicit_bump_is_seen(self):
        lead = self.lead("Bulk")
        self.assertEqual(self.total(), 1)
        # QuerySet.update() sends no signal; the repositories bump explicitly.
        DjangoLeadModel.objects.filter(id=lead.id).update(is_deleted=True)
        self.assertEqual(self.total(), 1)  # stale until the bump...
        count_cache.bump_affected(self.company.id, count_cache.LEADS)
        self.assertEqual(self.total(), 0)  # ...which the repository does

    def test_repository_queryset_update_bumps_the_total(self):
        from src.modules.leads.infrastructure.persistence.django_lead_repository import (
            DjangoLeadRepository,
        )

        new_owner = make_user(self.company, User.Role.ADMIN, "cache-new@example.com")
        self.lead("Mine")
        by_owner = [
            {"field": "owner", "operator": "equals", "value": str(new_owner.id)}
        ]
        self.assertEqual(self.total(filters=by_owner), 0)
        # QuerySet.update(): no signal, so the repository bumps explicitly.
        moved = DjangoLeadRepository(company_id=self.company.id).transfer_ownership(
            self.admin.id, new_owner.id
        )
        self.assertEqual(moved, 1)
        self.assertEqual(self.total(filters=by_owner), 1)

    def test_other_company_never_sees_or_reuses_the_total(self):
        self.lead("A1")
        self.lead("B1", company=self.other_company, owner=self.other_admin)
        self.lead("B2", company=self.other_company, owner=self.other_admin)
        self.assertEqual(self.total(), 1)
        self.assertEqual(self.total(self.other_client), 2)
        self.lead("A2")
        self.assertEqual(self.total(), 2)
        self.assertEqual(self.total(self.other_client), 2)

    def test_a_different_filter_gets_its_own_total(self):
        self.lead("Kochi lead", city="Kochi")
        self.lead("Other lead", city="Delhi")
        kochi = [{"field": "city", "operator": "equals", "value": "Kochi"}]
        self.assertEqual(self.total(), 2)
        self.assertEqual(self.total(filters=kochi), 1)
        self.assertEqual(self.total(), 2)

    def test_contact_write_changes_a_lead_total_filtered_on_contact_name(self):
        self.lead("John Smith")
        by_contact = [
            {"field": "contact_name", "operator": "equals", "value": "John Smith"}
        ]
        self.assertEqual(self.total(filters=by_contact), 0)
        now = timezone.now()
        DjangoContactModel.objects.create(
            company=self.company, contact_owner=self.admin, name="John Smith",
            created_by=self.admin, created_at=now,
            modified_by=self.admin, updated_at=now,
        )
        self.assertEqual(self.total(filters=by_contact), 1)

    def test_cache_failure_still_returns_the_right_total(self):
        self.lead("One")
        with mock.patch.object(count_cache.cache, "get", side_effect=RuntimeError("down")):
            self.assertEqual(self.total(), 1)
