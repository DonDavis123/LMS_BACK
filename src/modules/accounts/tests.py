from datetime import datetime, timezone

from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.users.infrastructure.persistence.models import User


class AccountApiTests(APITestCase):
    def setUp(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.owner = User.objects.create_user(
            email="account-owner@example.com",
            password="account-password",
            name="Account Owner",
            role=User.Role.ADMIN,
        )
        self.other_owner = User.objects.create_user(
            email="other-owner@example.com",
            password="other-password",
            name="Other Owner",
            role=User.Role.ADMIN,
        )

        self.account_one = DjangoAccountModel.objects.create(
            account_owner=self.owner,
            account_name="Alpha Technologies",
            account_number="ACC-001",
            account_site="alpha.example.com",
            account_type="Customer",
            annual_revenue=100000,
            billing_address="10 Main Street",
            billing_city="Kochi",
            billing_state="Kerala",
            billing_country="India",
            billing_postal_code="682001",
            created_by=self.owner,
            created_at=now,
            modified_by=self.owner,
            updated_at=now,
        )
        self.account_two = DjangoAccountModel.objects.create(
            account_owner=self.other_owner,
            account_name="Beta Industries",
            account_number="ACC-002",
            account_site="beta.example.com",
            account_type="Partner",
            annual_revenue=250000,
            billing_address="20 Park Road",
            billing_city="Bengaluru",
            billing_state="Karnataka",
            billing_country="India",
            billing_postal_code="560001",
            created_by=self.owner,
            created_at=now,
            modified_by=self.owner,
            updated_at=now,
        )
        DjangoAccountModel.objects.create(
            account_owner=self.owner,
            account_name="Gamma Services",
            account_number="ACC-003",
            account_site="gamma.example.com",
            account_type="Customer",
            annual_revenue=50000,
            billing_address="30 Lake Road",
            billing_city="Kochi",
            billing_state="Kerala",
            billing_country="India",
            billing_postal_code="682002",
            created_by=self.owner,
            created_at=now,
            modified_by=self.owner,
            updated_at=now,
        )

    def test_accounts_require_authentication(self):
        response = self.client.get("/api/accounts/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accounts_are_paginated(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get("/api/accounts/?page=1&page_size=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)
        self.assertEqual(response.data["pagination"]["page_size"], 2)
        self.assertEqual(response.data["pagination"]["total"], 3)
        self.assertEqual(response.data["pagination"]["total_pages"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_account_name_contains_filter(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(
            "/api/accounts/?filters=[{\"field\":\"account_name\",\"operator\":\"contains\",\"value\":\"alpha\"}]"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["account_name"] for item in response.data["results"]], ["Alpha Technologies"])

    def test_account_owner_and_numeric_filters(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(
            f"/api/accounts/?filters=[{{\"field\":\"account_owner\",\"operator\":\"equals\",\"value\":\"{self.owner.id}\"}}]"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 2)

        response = self.client.get(
            "/api/accounts/?filters=[{\"field\":\"annual_revenue\",\"operator\":\"after\",\"value\":100000}]"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["account_name"] for item in response.data["results"]], ["Beta Industries"])

    def test_account_multiple_filters_use_and_semantics(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(
            "/api/accounts/?filters=[{\"field\":\"account_type\",\"operator\":\"equals\",\"value\":\"Customer\"},{\"field\":\"billing_city\",\"operator\":\"equals\",\"value\":\"Kochi\"}]"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 2)

    def test_deleted_accounts_are_excluded_from_filtered_results(self):
        self.account_one.is_deleted = True
        self.account_one.save(update_fields=["is_deleted"])
        self.client.force_authenticate(self.owner)

        response = self.client.get(
            "/api/accounts/?filters=[{\"field\":\"account_name\",\"operator\":\"contains\",\"value\":\"Alpha\"}]"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["pagination"]["total"], 0)

    def test_invalid_account_filter_is_rejected(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(
            "/api/accounts/?filters=[{\"field\":\"password\",\"operator\":\"equals\",\"value\":\"secret\"}]"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
