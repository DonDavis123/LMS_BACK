import json
from unittest.mock import MagicMock, patch
from urllib import error

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from src.modules.authentication.infrastructure.email import HttpEmailService
from src.modules.authentication.infrastructure.email.reset_link import (
    build_reset_link,
)

HTTP = "src.modules.authentication.infrastructure.email.http_email_service"


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
    EMAIL_HTTP_ENDPOINT="https://mail.example.com/send",
    EMAIL_HTTP_TOKEN="secret-123",
    EMAIL_TIMEOUT=5,
)
class HttpEmailServiceTests(SimpleTestCase):
    @patch(f"{HTTP}.request.urlopen")
    def test_posts_reset_link_over_http(self, urlopen):
        urlopen.return_value = MagicMock()

        HttpEmailService().send_password_reset_email("user@example.com", "tok")

        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "https://mail.example.com/send")
        self.assertEqual(http_request.get_method(), "POST")
        self.assertEqual(http_request.get_header("Authorization"), "Bearer secret-123")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

        body = json.loads(http_request.data)
        link = "https://app.example.com/reset-password?token=tok"
        self.assertEqual(body["to"], "user@example.com")
        self.assertEqual(body["reset_link"], link)
        self.assertIn(link, body["text"])

    @override_settings(EMAIL_HTTP_TOKEN=None)
    @patch(f"{HTTP}.request.urlopen")
    def test_authorization_header_omitted_without_token(self, urlopen):
        urlopen.return_value = MagicMock()

        HttpEmailService().send_password_reset_email("user@example.com", "tok")

        http_request = urlopen.call_args.args[0]
        self.assertIsNone(http_request.get_header("Authorization"))

    @override_settings(EMAIL_HTTP_ENDPOINT=None)
    def test_missing_endpoint_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            HttpEmailService().send_password_reset_email("user@example.com", "tok")

    @override_settings(EMAIL_HTTP_ENDPOINT="ftp://mail.example.com")
    def test_non_http_endpoint_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            HttpEmailService().send_password_reset_email("user@example.com", "tok")

    @patch(f"{HTTP}.request.urlopen")
    def test_endpoint_rejection_is_raised(self, urlopen):
        urlopen.side_effect = error.HTTPError(
            "https://mail.example.com/send",
            401,
            "Unauthorized",
            {},
            MagicMock(read=lambda: b"bad token"),
        )
        with self.assertRaises(error.HTTPError):
            HttpEmailService().send_password_reset_email("user@example.com", "tok")
