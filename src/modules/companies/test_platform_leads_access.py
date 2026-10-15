from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.shared.tests.tenancy.factories import authenticated_client, make_user
from src.modules.users.infrastructure.persistence.models import User


class PlatformAdminLeadsAccessTests(APITestCase):

    def test_platform_admin_gets_403_on_leads_endpoints(self):
        client = authenticated_client(
            make_user(None, role=User.Role.PLATFORM_SUPERADMIN)
        )
        fake_id = "00000000-0000-0000-0000-000000000000"

        for method, url in (
            ("get", "/api/leads/"),
            ("post", "/api/leads/create/"),
            ("get", f"/api/leads/{fake_id}/"),
            ("patch", f"/api/leads/{fake_id}/update/"),
            ("delete", f"/api/leads/{fake_id}/delete/"),
            ("post", f"/api/leads/{fake_id}/convert/"),
            ("get", f"/api/leads/{fake_id}/conversion-check/"),
        ):
            with self.subTest(method=method, url=url):
                response = getattr(client, method)(url, {}, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
