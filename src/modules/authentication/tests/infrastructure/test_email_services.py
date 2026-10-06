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


def _response(body: bytes = b'{"ok": true}', url: str = "https://mail.example.com/send"):
    """Mimic the context-manager response returned by urlopen."""
    response = MagicMock()
    response.read.return_value = body
    response.geturl.return_value = url
    response.__enter__.return_value = response
    return response


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
        urlopen.return_value = _response()

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
        urlopen.return_value = _response()

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

    @patch(f"{HTTP}.request.urlopen")
    def test_relay_reported_failure_is_raised(self, urlopen):
        urlopen.return_value = _response(b'{"ok": false, "error": "quota"}')
        with self.assertRaises(RuntimeError):
            HttpEmailService().send_password_reset_email("user@example.com", "tok")

    @patch(f"{HTTP}.request.urlopen")
    def test_non_json_success_body_is_accepted(self, urlopen):
        urlopen.return_value = _response(b"OK")
        HttpEmailService().send_password_reset_email("user@example.com", "tok")


    @patch(f"{HTTP}.request.urlopen")
    def test_html_page_with_200_is_treated_as_failure(self, urlopen):
        # Google answers its sign-in page with HTTP 200 when the web app
        # is not public; nothing was sent.
        urlopen.return_value = _response(
            b"<!DOCTYPE html><html><title>Sign in</title></html>",
            url="https://accounts.google.com/signin?continue=x",
        )
        with self.assertLogs(HTTP, level="ERROR") as logs:
            with self.assertRaises(RuntimeError):
                HttpEmailService().send_password_reset_email(
                    "user@example.com", "tok"
                )
        self.assertIn("Anyone", logs.output[0])

    @patch(f"{HTTP}.request.urlopen")
    def test_rejection_log_never_contains_the_secret_key(self, urlopen):
        url = "https://script.google.com/macros/s/abc/exec?key=TOPSECRET"
        urlopen.side_effect = error.HTTPError(
            url,
            401,
            "Unauthorized",
            {},
            MagicMock(read=lambda: b"<html><title>Error</title></html>"),
        )
        with self.assertLogs(HTTP, level="ERROR") as logs:
            with self.assertRaises(error.HTTPError):
                HttpEmailService().send_password_reset_email(
                    "user@example.com", "tok"
                )
        self.assertNotIn("TOPSECRET", logs.output[0])
        self.assertIn("HTTP 401", logs.output[0])
