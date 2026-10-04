import json
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.users.infrastructure.persistence.models import User


class UserListApiTestCase(APITestCase):
    URL = "/api/users/"

    def setUp(self):
        self.superadmin = self.make(
            "superadmin@example.com", "Super Admin", User.Role.SUPERADMIN,
        )
        self.alice = self.make("alice@acme.com", "Alice Johnson", User.Role.ADMIN)
        self.bob = self.make("bob@globex.com", "bob smith", User.Role.ADMIN)
        self.carol = self.make(
            "carol@acme.com", "Carol White", User.Role.SUPERADMIN, is_active=False,
        )
        self.dave = self.make(
            "dave@initech.com", "Dave Brown", User.Role.ADMIN, is_active=False,
        )

        # Deterministic creation order: superadmin oldest ... dave newest.
        now = timezone.now()
        for offset, user in enumerate(
            (self.superadmin, self.alice, self.bob, self.carol, self.dave),
        ):
            User.objects.filter(id=user.id).update(
                created_at=now - timedelta(days=10 - offset),
            )

        self.client.force_authenticate(self.superadmin)

    @staticmethod
    def make(email, name, role, is_active=True):
        return User.objects.create_user(
            email=email,
            password="password123",
            name=name,
            role=role,
            is_active=is_active,
        )

    def get(self, **params):
        if "filters" in params and not isinstance(params["filters"], str):
            params["filters"] = json.dumps(params["filters"])
        return self.client.get(self.URL, params)

    @staticmethod
    def emails(response):
        return [item["email"] for item in response.data["results"]]


class UserListSearchTests(UserListApiTestCase):

    def test_search_matches_name_case_insensitively(self):
        response = self.get(search="ALICE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.emails(response), ["alice@acme.com"])
        self.assertEqual(response.data["pagination"]["total"], 1)

    def test_search_matches_name_by_substring(self):
        response = self.get(search="smi")

        self.assertEqual(self.emails(response), ["bob@globex.com"])

    def test_search_matches_email(self):
        response = self.get(search="initech")

        self.assertEqual(self.emails(response), ["dave@initech.com"])

    def test_search_matches_name_or_email(self):
        response = self.get(search="acme")

        self.assertEqual(
            sorted(self.emails(response)),
            ["alice@acme.com", "carol@acme.com"],
        )

    def test_search_with_no_match_returns_empty_page(self):
        response = self.get(search="nobody-here")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["pagination"]["total"], 0)
        self.assertEqual(response.data["pagination"]["total_pages"], 0)

    def test_blank_search_is_ignored(self):
        response = self.get(search="   ")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 5)

    def test_search_treats_wildcards_literally(self):
        response = self.get(search="%")

        self.assertEqual(response.data["pagination"]["total"], 0)

    def test_overlong_search_is_rejected(self):
        response = self.get(search="a" * 101)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)


class UserListFilterTests(UserListApiTestCase):

    def test_filter_by_role(self):
        response = self.get(
            filters=[{"field": "role", "operator": "equals", "value": "SUPERADMIN"}],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            sorted(self.emails(response)),
            ["carol@acme.com", "superadmin@example.com"],
        )

    def test_filter_by_role_in(self):
        response = self.get(
            filters=[
                {"field": "role", "operator": "in", "value": ["ADMIN", "SUPERADMIN"]},
            ],
        )

        self.assertEqual(response.data["pagination"]["total"], 5)

    def test_filter_by_active_status(self):
        response = self.get(
            filters=[{"field": "is_active", "operator": "equals", "value": True}],
        )

        self.assertEqual(
            sorted(self.emails(response)),
            ["alice@acme.com", "bob@globex.com", "superadmin@example.com"],
        )

    def test_filter_by_inactive_status(self):
        response = self.get(
            filters=[{"field": "is_active", "operator": "equals", "value": False}],
        )

        self.assertEqual(
            sorted(self.emails(response)),
            ["carol@acme.com", "dave@initech.com"],
        )

    def test_combined_role_and_status_filters(self):
        response = self.get(
            filters=[
                {"field": "role", "operator": "equals", "value": "ADMIN"},
                {"field": "is_active", "operator": "equals", "value": False},
            ],
        )

        self.assertEqual(self.emails(response), ["dave@initech.com"])

    def test_search_combined_with_filters(self):
        response = self.get(
            search="acme",
            filters=[{"field": "is_active", "operator": "equals", "value": False}],
        )

        self.assertEqual(self.emails(response), ["carol@acme.com"])
        self.assertEqual(response.data["pagination"]["total"], 1)

    def test_text_filter_on_email(self):
        response = self.get(
            filters=[{"field": "email", "operator": "contains", "value": "GLOBEX"}],
        )

        self.assertEqual(self.emails(response), ["bob@globex.com"])

    def test_invalid_filters_are_rejected_with_400(self):
        invalid = {
            "unknown field": [{"field": "password", "operator": "equals", "value": "x"}],
            "deleted_at is not exposed": [
                {"field": "deleted_at", "operator": "equals", "value": "x"},
            ],
            "invalid role": [{"field": "role", "operator": "equals", "value": "OWNER"}],
            "role operator": [{"field": "role", "operator": "contains", "value": "ADMIN"}],
            "role list": [{"field": "role", "operator": "in", "value": []}],
            "status not boolean": [
                {"field": "is_active", "operator": "equals", "value": "yes"},
            ],
            "status operator": [
                {"field": "is_active", "operator": "contains", "value": True},
            ],
            "empty text": [{"field": "name", "operator": "contains", "value": ""}],
            "missing value": [{"field": "role", "operator": "equals"}],
        }

        for label, filters in invalid.items():
            with self.subTest(label):
                response = self.get(filters=filters)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("detail", response.data)

    def test_malformed_filters_json_is_rejected_with_400(self):
        for raw in ("{not json", '{"field": "role"}'):
            with self.subTest(raw=raw):
                response = self.get(filters=raw)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserListSortingTests(UserListApiTestCase):

    def test_default_order_is_newest_first(self):
        response = self.get()

        self.assertEqual(
            self.emails(response),
            [
                "dave@initech.com",
                "carol@acme.com",
                "bob@globex.com",
                "alice@acme.com",
                "superadmin@example.com",
            ],
        )

    def test_sort_by_name_is_case_insensitive(self):
        asc = self.get(sort_by="name", sort_direction="asc")
        desc = self.get(sort_by="name", sort_direction="desc")

        self.assertEqual(
            [item["name"] for item in asc.data["results"]],
            ["Alice Johnson", "bob smith", "Carol White", "Dave Brown", "Super Admin"],
        )
        self.assertEqual(
            [item["name"] for item in desc.data["results"]],
            ["Super Admin", "Dave Brown", "Carol White", "bob smith", "Alice Johnson"],
        )

    def test_sort_by_email(self):
        response = self.get(sort_by="email", sort_direction="asc")

        self.assertEqual(
            self.emails(response),
            [
                "alice@acme.com",
                "bob@globex.com",
                "carol@acme.com",
                "dave@initech.com",
                "superadmin@example.com",
            ],
        )

    def test_sort_by_role(self):
        response = self.get(sort_by="role", sort_direction="asc")
        roles = [item["role"] for item in response.data["results"]]

        self.assertEqual(roles, ["ADMIN", "ADMIN", "ADMIN", "SUPERADMIN", "SUPERADMIN"])

    def test_sort_by_is_active(self):
        response = self.get(sort_by="is_active", sort_direction="desc")
        flags = [item["is_active"] for item in response.data["results"]]

        self.assertEqual(flags, [True, True, True, False, False])

    def test_sort_by_created_at(self):
        response = self.get(sort_by="created_at", sort_direction="asc")

        self.assertEqual(self.emails(response)[0], "superadmin@example.com")
        self.assertEqual(self.emails(response)[-1], "dave@initech.com")

    def test_sorting_applies_to_filtered_results(self):
        response = self.get(
            sort_by="name",
            sort_direction="desc",
            filters=[{"field": "role", "operator": "equals", "value": "ADMIN"}],
        )

        self.assertEqual(
            self.emails(response),
            ["dave@initech.com", "bob@globex.com", "alice@acme.com"],
        )

    def test_invalid_sort_values_are_rejected_with_400(self):
        for params in (
            {"sort_by": "password"},
            {"sort_by": "deleted_at"},
            {"sort_by": "name", "sort_direction": "sideways"},
        ):
            with self.subTest(params=params):
                response = self.get(**params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("detail", response.data)


class UserListPaginationTests(UserListApiTestCase):

    def test_pagination_keeps_existing_contract(self):
        response = self.get(page=1, page_size=2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"results", "pagination"})
        self.assertEqual(
            response.data["pagination"],
            {"page": 1, "page_size": 2, "total": 5, "total_pages": 3},
        )
        self.assertEqual(len(response.data["results"]), 2)

    def test_pages_do_not_overlap_when_sorted(self):
        seen = []
        for page in (1, 2, 3):
            response = self.get(
                page=page, page_size=2, sort_by="role", sort_direction="asc",
            )
            seen.extend(self.emails(response))

        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)

    def test_total_reflects_filters_not_the_whole_table(self):
        response = self.get(
            page=1,
            page_size=1,
            filters=[{"field": "is_active", "operator": "equals", "value": False}],
        )

        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertEqual(response.data["pagination"]["total_pages"], 2)

    def test_invalid_pagination_is_rejected_with_400(self):
        for params in ({"page": 0}, {"page": "abc"}, {"page_size": 51}):
            with self.subTest(params=params):
                response = self.get(**params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserListResponseShapeTests(UserListApiTestCase):

    def test_item_keeps_existing_fields_and_adds_created_at(self):
        response = self.get(search="alice")

        self.assertEqual(
            set(response.data["results"][0]),
            {"id", "name", "email", "role", "is_active", "created_at"},
        )
        item = response.data["results"][0]
        self.assertEqual(item["id"], str(self.alice.id))
        self.assertEqual(item["name"], "Alice Johnson")
        self.assertEqual(item["role"], "ADMIN")
        self.assertTrue(item["is_active"])
        self.assertTrue(item["created_at"])


class UserListSoftDeleteTests(UserListApiTestCase):

    def setUp(self):
        super().setUp()
        User.objects.filter(id=self.bob.id).update(
            deleted_at=timezone.now(), is_active=False,
        )

    def test_soft_deleted_user_is_not_listed(self):
        response = self.get()

        self.assertNotIn("bob@globex.com", self.emails(response))
        self.assertEqual(response.data["pagination"]["total"], 4)

    def test_soft_deleted_user_is_not_found_by_search(self):
        self.assertEqual(self.get(search="bob").data["results"], [])
        self.assertEqual(self.get(search="globex").data["results"], [])

    def test_soft_deleted_user_is_not_found_by_filters(self):
        response = self.get(
            filters=[{"field": "is_active", "operator": "equals", "value": False}],
        )

        self.assertNotIn("bob@globex.com", self.emails(response))
        self.assertEqual(response.data["pagination"]["total"], 2)

    def test_soft_deleted_user_is_not_counted_when_sorting(self):
        response = self.get(sort_by="email", sort_direction="asc")

        self.assertNotIn("bob@globex.com", self.emails(response))
        self.assertEqual(response.data["pagination"]["total"], 4)


class UserListPermissionTests(UserListApiTestCase):

    def test_admin_is_forbidden(self):
        self.client.force_authenticate(self.alice)

        response = self.get(search="alice")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_unauthorized(self):
        self.client.force_authenticate(None)

        response = self.get()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
