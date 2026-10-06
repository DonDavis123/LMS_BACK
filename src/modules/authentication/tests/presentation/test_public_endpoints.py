from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

VIEWS = "src.modules.authentication.presentation.api.views"
STALE = {"HTTP_AUTHORIZATION": "Bearer expired.or.invalid"}


@override_settings(ALLOWED_HOSTS=["testserver"])
class PublicPasswordEndpointsTests(SimpleTestCase):
    """A stale Bearer token must not block the public reset flow."""

    @patch(f"{VIEWS}.forgot_password.get_forgot_password_use_case")
    def test_forgot_password_ignores_stale_token(self, get_use_case):
        get_use_case.return_value = Mock()

        response = APIClient().post(
            "/api/auth/forgot-password/",
            {"email": "user@example.com"},
            format="json",
            **STALE,
        )

        self.assertEqual(response.status_code, 200)

    @patch(f"{VIEWS}.reset_password.get_reset_password_use_case")
    def test_reset_password_ignores_stale_token(self, get_use_case):
        get_use_case.return_value = Mock()

        response = APIClient().post(
            "/api/auth/reset-password/",
            {"token": "tok", "new_password": "NewPassw0rd!"},
            format="json",
            **STALE,
        )

        self.assertEqual(response.status_code, 200)
