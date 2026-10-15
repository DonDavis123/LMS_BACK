from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User


class CurrentUserCompanyTests(APITestCase):

    def test_company_user_gets_company_info(self):
        company = make_company("Acme")
        user = make_user(company, role=User.Role.ADMIN)

        response = authenticated_client(user).get("/api/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], user.email)
        self.assertEqual(response.data["role"], "ADMIN")
        self.assertEqual(
            response.data["company"],
            {"id": str(company.id), "name": "Acme", "status": "ACTIVE"},
        )

    def test_platform_admin_gets_null_company(self):
        user = make_user(None, role=User.Role.PLATFORM_SUPERADMIN)

        response = authenticated_client(user).get("/api/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "PLATFORM_SUPERADMIN")
        self.assertIsNone(response.data["company"])
