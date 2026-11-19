import json
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.shared.tests.tenancy.factories import default_test_company
from src.modules.users.infrastructure.persistence.models import User


def _aware(year, month, day, hour=0, minute=0, second=0):
    return timezone.make_aware(datetime(year, month, day, hour, minute, second))


def _f(operator, value, field="created_at"):
    return {"field": field, "operator": operator, "value": value}


class _CreatedRangeMixin:
    """
    The list screens send the day pickers as a `created_at` filter made of
    plain "YYYY-MM-DD" strings. Both ends are whole calendar days in the
    project's time zone, so "today -> today" must return today's records.
    """

    URL = ""
    NAME_KEY = ""

    def setUp(self):
        self.user = User.objects.create_user(
            company=default_test_company(),
            email="range-owner@example.com",
            password="range-password",
            name="Range Owner",
            role=User.Role.ADMIN,
        )
        self.client.force_authenticate(self.user)

    def make(self, name, created_at):
        raise NotImplementedError

    def names(self, filters):
        response = self.client.get(self.URL, {"filters": json.dumps(filters)})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return sorted(item[self.NAME_KEY] for item in response.data["results"])

    def test_same_day_range_returns_the_whole_day(self):
        self.make("first-instant", _aware(2026, 9, 15, 0, 0, 0))
        self.make("last-second", _aware(2026, 9, 15, 23, 59, 59))
        self.make("day-before", _aware(2026, 9, 14, 23, 59, 59))
        self.make("day-after", _aware(2026, 9, 16, 0, 0, 0))

        names = self.names([_f("between", {"from": "2026-09-15", "to": "2026-09-15"})])
        self.assertEqual(names, ["first-instant", "last-second"])

    def test_multi_day_range_is_inclusive_of_last_day(self):
        self.make("in-1", _aware(2026, 9, 1, 0, 0, 0))
        self.make("in-2", _aware(2026, 9, 30, 23, 59, 59))
        self.make("out-1", _aware(2026, 10, 1, 0, 0, 0))
        self.make("out-2", _aware(2026, 8, 31, 23, 59, 59))

        names = self.names([_f("between", {"from": "2026-09-01", "to": "2026-09-30"})])
        self.assertEqual(names, ["in-1", "in-2"])

    def test_from_only_and_to_only(self):
        self.make("old", _aware(2026, 9, 10, 12))
        self.make("new", _aware(2026, 9, 20, 12))

        self.assertEqual(self.names([_f("after", "2026-09-20")]), ["new"])
        # "on/before" includes the whole of the named day.
        self.assertEqual(self.names([_f("before", "2026-09-10")]), ["old"])

    def test_reversed_range_is_rejected(self):
        response = self.client.get(
            self.URL,
            {"filters": json.dumps([_f("between", {"from": "2026-09-30", "to": "2026-09-01"})])},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_is_rejected(self):
        response = self.client.get(
            self.URL, {"filters": json.dumps([_f("after", "not-a-date")])}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ContactCreatedRangeFilterTests(_CreatedRangeMixin, APITestCase):
    URL = "/api/contacts/"
    NAME_KEY = "name"

    def make(self, name, created_at):
        return DjangoContactModel.objects.create(
            company=default_test_company(),
            contact_owner=self.user,
            name=name,
            created_by=self.user,
            created_at=created_at,
            modified_by=self.user,
            updated_at=created_at,
        )


class AccountCreatedRangeFilterTests(_CreatedRangeMixin, APITestCase):
    URL = "/api/accounts/"
    NAME_KEY = "account_name"

    def make(self, name, created_at):
        return DjangoAccountModel.objects.create(
            company=default_test_company(),
            account_owner=self.user,
            account_name=name,
            created_by=self.user,
            created_at=created_at,
            modified_by=self.user,
            updated_at=created_at,
        )
