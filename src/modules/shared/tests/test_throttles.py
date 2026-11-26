from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import SimpleRateThrottle

from src.modules.shared.presentation.exception_handler import throttled_message
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

AUTH_VIEWS = "src.modules.authentication.presentation.api.views"
LEAD_SUMMARY = "src.modules.leads.presentation.api.views.lead_summary"
CONTACT_SUMMARY = "src.modules.contacts.presentation.api.views.contact_summary"
ACCOUNT_SUMMARY = "src.modules.accounts.presentation.api.views.account_summary"
BRIEFING = "src.modules.dashboard.presentation.api.views.daily_briefing"
TRANSCRIPT = "src.modules.calls.presentation.api.views.call_recording_transcript"

LOGIN = "/api/auth/login/"
FORGOT = "/api/auth/forgot-password/"
RESET = "/api/auth/reset-password/"


def with_rates(**rates):
    """override_settings that changes only the given throttle rates."""
    merged = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], **rates}
    return override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": merged,
        }
    )


class ThrottledMessageTests(SimpleTestCase):
    def test_seconds_minutes_hours(self):
        self.assertIn("30 seconds", throttled_message(29.2))
        self.assertIn("about 1 minute", throttled_message(60))
        self.assertIn("about 15 minutes", throttled_message(14 * 60 + 5))
        self.assertIn("about 1 hour", throttled_message(3600))
        self.assertIn("about 2 hours", throttled_message(3601))

    def test_unknown_wait(self):
        self.assertEqual(
            throttled_message(None), "Too many requests. Please try again later."
        )


class ThrottleTestCase(APITestCase):
    def setUp(self):
        # Throttle counters live in the cache: start every test clean.
        cache.clear()
        self.addCleanup(cache.clear)


class AuthThrottleTests(ThrottleTestCase):
    def login(self, email, password="wrong-password"):
        return APIClient().post(
            LOGIN, {"email": email, "password": password}, format="json"
        )

    @with_rates(auth_login_email="2/hour")
    def test_login_is_limited_per_email(self):
        make_user(make_company("Login Co"), User.Role.ADMIN, "victim@example.com")

        self.assertEqual(
            self.login("victim@example.com").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.login("victim@example.com").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        throttled = self.login("victim@example.com")
        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", throttled.headers)
        self.assertTrue(throttled.json()["detail"].startswith("Too many requests."))

        # Even the right password is refused while the email is locked ...
        self.assertEqual(
            self.login("victim@example.com", "password123").status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        # ... and another email is not affected.
        self.assertEqual(
            self.login("someone-else@example.com").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @with_rates(auth_login_email="1/hour")
    def test_login_email_key_ignores_case_and_spaces(self):
        self.assertEqual(
            self.login("Mixed@Example.com").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.login("  mixed@example.COM ").status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @with_rates(auth_login_ip="2/hour")
    def test_login_is_limited_per_ip_across_emails(self):
        self.assertEqual(
            self.login("a@example.com").status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.login("b@example.com").status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.login("c@example.com").status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @with_rates(auth_login_ip="1/hour", auth_login_email="1/hour")
    def test_login_without_email_only_uses_the_ip_limit(self):
        client = APIClient()
        first = client.post(LOGIN, {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_400_BAD_REQUEST)
        second = client.post(LOGIN, {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @with_rates(auth_forgot_password_email="2/hour")
    @patch(f"{AUTH_VIEWS}.forgot_password.get_forgot_password_use_case")
    def test_forgot_password_is_limited_per_email(self, get_use_case):
        use_case = get_use_case.return_value = Mock()
        client = APIClient()
        body = {"email": "spam-target@example.com"}

        self.assertEqual(
            client.post(FORGOT, body, format="json").status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            client.post(FORGOT, body, format="json").status_code, status.HTTP_200_OK
        )
        throttled = client.post(FORGOT, body, format="json")

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # No third email was sent.
        self.assertEqual(use_case.execute.call_count, 2)
        # A different address is still served.
        self.assertEqual(
            client.post(
                FORGOT, {"email": "other@example.com"}, format="json"
            ).status_code,
            status.HTTP_200_OK,
        )

    @with_rates(auth_forgot_password_ip="2/hour")
    @patch(f"{AUTH_VIEWS}.forgot_password.get_forgot_password_use_case")
    def test_forgot_password_is_limited_per_ip(self, get_use_case):
        get_use_case.return_value = Mock()
        client = APIClient()

        for index in range(2):
            self.assertEqual(
                client.post(
                    FORGOT, {"email": f"u{index}@example.com"}, format="json"
                ).status_code,
                status.HTTP_200_OK,
            )
        self.assertEqual(
            client.post(
                FORGOT, {"email": "u3@example.com"}, format="json"
            ).status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @with_rates(auth_reset_password_ip="2/hour")
    @patch(f"{AUTH_VIEWS}.reset_password.get_reset_password_use_case")
    def test_reset_password_is_limited_per_ip(self, get_use_case):
        get_use_case.return_value = Mock()
        client = APIClient()
        body = {"token": "tok", "new_password": "NewPassw0rd!"}

        self.assertEqual(
            client.post(RESET, body, format="json").status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            client.post(RESET, body, format="json").status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            client.post(RESET, body, format="json").status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @with_rates(auth_login_email="1/hour", auth_login_ip="1/hour")
    def test_throttle_fails_open_when_the_cache_is_down(self):
        broken = Mock()
        broken.get.side_effect = RuntimeError("redis is down")
        broken.set.side_effect = RuntimeError("redis is down")

        with patch.object(SimpleRateThrottle, "cache", broken):
            responses = [self.login("down@example.com") for _ in range(3)]

        # A normal "wrong password" answer, never a 429 or a 500.
        self.assertEqual(
            {response.status_code for response in responses},
            {status.HTTP_401_UNAUTHORIZED},
        )


class GeminiThrottleTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.company = make_company("AI Co")
        self.user = make_user(self.company, User.Role.ADMIN, "ai-1@example.com")
        self.colleague = make_user(self.company, User.Role.ADMIN, "ai-2@example.com")
        self.client_1 = authenticated_client(self.user)
        self.client_2 = authenticated_client(self.colleague)

    @staticmethod
    def not_found_use_case():
        use_case = Mock()
        use_case.execute.side_effect = ValueError("Not found.")
        return use_case

    @with_rates(ai_generation_user="2/hour")
    def test_summary_posts_are_limited_per_user_but_gets_are_free(self):
        lead_url = f"/api/leads/{uuid4()}/summary/"
        generate = self.not_found_use_case()

        with patch(
            f"{LEAD_SUMMARY}.get_generate_lead_summary_use_case",
            return_value=generate,
        ), patch(
            f"{LEAD_SUMMARY}.get_lead_summary_use_case",
            return_value=self.not_found_use_case(),
        ):
            # Reads do not count, however many there are.
            for _ in range(5):
                self.assertEqual(
                    self.client_1.get(lead_url).status_code,
                    status.HTTP_404_NOT_FOUND,
                )

            for _ in range(2):
                self.assertEqual(
                    self.client_1.post(lead_url, {}, format="json").status_code,
                    status.HTTP_404_NOT_FOUND,
                )
            throttled = self.client_1.post(lead_url, {}, format="json")

            self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("Retry-After", throttled.headers)
            self.assertEqual(generate.execute.call_count, 2)

            # The colleague has their own allowance.
            self.assertEqual(
                self.client_2.post(lead_url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )

    @with_rates(ai_generation_user="100/hour", ai_generation_company="3/hour")
    def test_company_limit_is_shared_by_all_its_users(self):
        lead_url = f"/api/leads/{uuid4()}/summary/"

        with patch(
            f"{LEAD_SUMMARY}.get_generate_lead_summary_use_case",
            return_value=self.not_found_use_case(),
        ):
            self.assertEqual(
                self.client_1.post(lead_url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )
            self.assertEqual(
                self.client_2.post(lead_url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )
            self.assertEqual(
                self.client_1.post(lead_url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )
            self.assertEqual(
                self.client_2.post(lead_url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Another company is not affected.
        other = make_company("Other AI Co")
        other_client = authenticated_client(
            make_user(other, User.Role.ADMIN, "ai-other@example.com")
        )
        with patch(
            f"{LEAD_SUMMARY}.get_generate_lead_summary_use_case",
            return_value=self.not_found_use_case(),
        ):
            self.assertEqual(
                other_client.post(lead_url, {}, format="json").status_code,
                status.HTTP_404_NOT_FOUND,
            )

    @with_rates(ai_generation_user="1/hour")
    def test_summaries_and_briefing_share_one_bucket(self):
        contact_url = f"/api/contacts/{uuid4()}/summary/"
        account_url = f"/api/accounts/{uuid4()}/summary/"

        with patch(
            f"{CONTACT_SUMMARY}.get_generate_contact_summary_use_case",
            return_value=self.not_found_use_case(),
        ), patch(
            f"{ACCOUNT_SUMMARY}.get_generate_account_summary_use_case",
            return_value=self.not_found_use_case(),
        ), patch(
            f"{BRIEFING}.get_daily_briefing_use_case",
            return_value=self.not_found_use_case(),
        ):
            self.assertNotEqual(
                self.client_1.post(contact_url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
            self.assertEqual(
                self.client_1.post(account_url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
            self.assertEqual(
                self.client_1.post(
                    "/api/dashboard/briefing/", {}, format="json"
                ).status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

    @with_rates(ai_transcription_user="1/hour", ai_generation_user="100/hour")
    def test_transcription_has_its_own_bucket_and_polling_is_free(self):
        url = f"/api/calls/{uuid4()}/recordings/{uuid4()}/transcript/"
        lead_url = f"/api/leads/{uuid4()}/summary/"
        request_use_case = self.not_found_use_case()

        with patch(
            f"{TRANSCRIPT}.get_request_recording_transcription_use_case",
            return_value=request_use_case,
        ), patch(
            f"{TRANSCRIPT}.get_recording_transcript_use_case",
            return_value=self.not_found_use_case(),
        ), patch(
            f"{LEAD_SUMMARY}.get_generate_lead_summary_use_case",
            return_value=self.not_found_use_case(),
        ):
            for _ in range(4):
                self.assertNotEqual(
                    self.client_1.get(url).status_code,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                )

            self.assertNotEqual(
                self.client_1.post(url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
            self.assertEqual(
                self.client_1.post(url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
            self.assertEqual(request_use_case.execute.call_count, 1)

            # Summaries use a different bucket and are still available.
            self.assertNotEqual(
                self.client_1.post(lead_url, {}, format="json").status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
