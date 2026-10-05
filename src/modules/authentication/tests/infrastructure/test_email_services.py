import json
from unittest.mock import MagicMock, patch
from urllib import error

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from src.modules.authentication.infrastructure.email import BrevoEmailService
from src.modules.authentication.infrastructure.email.reset_link import (
    build_reset_link,
)

BREVO = "src.modules.authentication.infrastructure.email.brevo_email_service"


@override_settings(FRONTEND_URL="https://app.example.com/")
class ResetLinkTests(SimpleTestCase):
    def test_trailing_slash_is_removed_and_token_encoded(self):
        self.assertEqual(
            build_reset_link("a b"),
            "https://app.example.com/reset-password?token=a%20b",
        )

    @override_settings(FRONTEND_URL=None)
    def test_missing_frontend_url_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            build_reset_link("token")


@override_settings(
    FRONTEND_URL="https://app.example.com",
    BREVO_API_KEY="key-123",
    DEFAULT_FROM_EMAIL="LeadPulse <noreply@example.com>",
    EMAIL_TIMEOUT=5,
)
class BrevoEmailServiceTests(SimpleTestCase):
    @patch(f"{BREVO}.request.urlopen")
    def test_sends_over_https_api(self, urlopen):
        urlopen.return_value = MagicMock()

        BrevoEmailService().send_password_reset_email("user@example.com", "tok")

        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(http_request.get_header("Api-key"), "key-123")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

        body = json.loads(http_request.data)
        self.assertEqual(body["sender"]["email"], "noreply@example.com")
        self.assertEqual(body["to"], [{"email": "user@example.com"}])
        self.assertIn("https://app.example.com/reset-password?token=tok", body["textContent"])

    @override_settings(BREVO_API_KEY=None)
    def test_missing_api_key_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            BrevoEmailService().send_password_reset_email("user@example.com", "tok")

    @patch(f"{BREVO}.request.urlopen")
    def test_provider_rejection_is_raised(self, urlopen):
        urlopen.side_effect = error.HTTPError(
            "https://api.brevo.com", 401, "Unauthorized", {}, MagicMock(read=lambda: b"bad key")
        )
        with self.assertRaises(error.HTTPError):
            BrevoEmailService().send_password_reset_email("user@example.com", "tok")
