from datetime import timedelta

from django.db import connection
from django.utils import timezone
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

OVERVIEW = "/api/platform/overview/"
Status = DjangoCompanyModel.Status


class PlatformOverviewApiTests(APITestCase):

    def setUp(self):
        self.platform_admin = make_user(
            None, role=User.Role.PLATFORM_SUPERADMIN, email="platform@example.com"
        )
        self.client = authenticated_client(self.platform_admin)

    def test_empty_platform(self):
        response = self.client.get(OVERVIEW)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["companies"],
            {"total": 0, "active": 0, "onboarding": 0, "suspended": 0},
        )
        self.assertEqual(response.data["users"], {"total": 0, "active": 0})
        self.assertEqual(response.data["recent_companies"], [])

    def test_counts_exclude_platform_admins(self):
        make_user(None, role=User.Role.PLATFORM_SUPERADMIN, email="p2@example.com")
        active = make_company("A", status=Status.ACTIVE)
        make_company("B", status=Status.ACTIVE)
        make_company("C", status=Status.ONBOARDING)
        make_company("D", status=Status.SUSPENDED)
        make_user(active, role=User.Role.SUPERADMIN)
        make_user(active, role=User.Role.ADMIN)
        make_user(active, role=User.Role.ADMIN, is_active=False)

        response = self.client.get(OVERVIEW)

        self.assertEqual(
            response.data["companies"],
            {"total": 4, "active": 2, "onboarding": 1, "suspended": 1},
        )
        self.assertEqual(response.data["users"], {"total": 3, "active": 2})

    def test_recent_companies_are_the_last_five_newest_first(self):
        # Distinct, explicit creation times: back-to-back inserts can share
        # one timestamp on platforms with a coarse clock (e.g. Windows).
        base = timezone.now() - timedelta(days=1)
        for index in range(7):
            company = make_company(f"Company {index}")
            DjangoCompanyModel.objects.filter(pk=company.pk).update(
                created_at=base + timedelta(minutes=index)
            )

        recent = self.client.get(OVERVIEW).data["recent_companies"]

        self.assertEqual(len(recent), 5)
        self.assertEqual(
            [c["name"] for c in recent],
            [f"Company {i}" for i in (6, 5, 4, 3, 2)],
        )
        self.assertEqual(set(recent[0]), {"id", "name", "status", "created_at"})

    def test_chart_data(self):
        a = make_company("Alpha", status=Status.ACTIVE)
        b = make_company("Beta", status=Status.ACTIVE)
        make_user(a, role=User.Role.SUPERADMIN)
        make_user(a, role=User.Role.ADMIN)
        make_user(b, role=User.Role.ADMIN)

        data = self.client.get(OVERVIEW).data

        self.assertEqual(len(data["companies_growth"]), 6)
        self.assertEqual(data["companies_growth"][-1]["count"], 2)
        self.assertEqual(sum(row["count"] for row in data["companies_growth"]), 2)
        self.assertEqual(
            {row["role"]: row["count"] for row in data["users_by_role"]},
            {"ADMIN": 2, "SUPERADMIN": 1},
        )
        self.assertEqual(
            [(c["name"], c["users_count"]) for c in data["top_companies"]],
            [("Alpha", 2), ("Beta", 1)],
        )

    def test_query_count_is_constant(self):
        for index in range(6):
            make_user(make_company(f"C{index}"))

        # actor lookup + 2 aggregates + recent list + growth + roles + top
        # companies; independent of data size.
        with CaptureQueriesContext(connection) as queries:
            self.client.get(OVERVIEW)
        self.assertLessEqual(len(queries), 8)

    def test_non_platform_users_are_forbidden(self):
        company = make_company("Tenant")
        for role in (User.Role.SUPERADMIN, User.Role.ADMIN):
            with self.subTest(role=role):
                client = authenticated_client(make_user(company, role=role))
                self.assertEqual(
                    client.get(OVERVIEW).status_code, status.HTTP_403_FORBIDDEN
                )
        self.assertIn(
            APIClient().get(OVERVIEW).status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )
