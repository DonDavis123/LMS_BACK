from django.test import SimpleTestCase

from src.modules.authentication.infrastructure.email.relay_diagnostics import (
    hint_for_failure,
    is_html,
    safe_url,
    summarize_body,
)

GOOGLE_PAGE = (
    "<!DOCTYPE html><html><head><title>Sign in - Google Accounts</title>"
    "</head><body>...</body></html>"
)


class SafeUrlTests(SimpleTestCase):
    def test_query_string_with_secret_is_dropped(self):
        self.assertEqual(
            safe_url("https://script.google.com/macros/s/abc/exec?key=SECRET"),
            "https://script.google.com/macros/s/abc/exec",
        )

    def test_missing_url(self):
        self.assertEqual(safe_url(None), "unknown")


class SummarizeBodyTests(SimpleTestCase):
    def test_html_is_reduced_to_its_title(self):
        self.assertEqual(
            summarize_body(GOOGLE_PAGE),
            "HTML page titled 'Sign in - Google Accounts'",
        )

    def test_plain_text_is_collapsed_and_truncated(self):
        self.assertEqual(summarize_body("a\n  b"), "a b")
        self.assertEqual(len(summarize_body("x" * 500)), 200)

    def test_is_html(self):
        self.assertTrue(is_html(GOOGLE_PAGE))
        self.assertFalse(is_html('{"ok": true}'))


class HintTests(SimpleTestCase):
    def test_sign_in_redirect(self):
        hint = hint_for_failure(200, "https://accounts.google.com/signin", GOOGLE_PAGE)
        self.assertIn("Anyone", hint)

    def test_html_401_points_to_deployment_access(self):
        hint = hint_for_failure(401, "https://script.google.com/x", GOOGLE_PAGE)
        self.assertIn("Who has access: Anyone", hint)

    def test_html_404(self):
        self.assertIn("/exec", hint_for_failure(404, None, GOOGLE_PAGE))

    def test_non_html_401_points_to_token(self):
        self.assertIn("EMAIL_HTTP_TOKEN", hint_for_failure(401, None, "denied"))

    def test_unknown_failure_has_no_hint(self):
        self.assertEqual(hint_for_failure(500, None, "boom"), "")
