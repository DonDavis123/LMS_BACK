from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_model import (
    DjangoLeadFormModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

FORM = "/api/lead-capture/form/"
PUBLIC = "/api/public/lead-forms/"
CLOSED = "This form is no longer accepting responses"
MESSAGE = "I would like a demo next week."


def payload(**extra):
    return {
        "name": "Visitor One",
        "email": "visitor@example.com",
        "phone": "9876543210",
        "description": MESSAGE,
        **extra,
    }


class PublicLeadFormTests(APITestCase):
    def setUp(self):
        # Throttle counters live in the cache: start every test clean.
        cache.clear()
        self.addCleanup(cache.clear)
        self.company = make_company("Public Co", "public-co")
        self.super = make_user(self.company, User.Role.SUPERADMIN, "pub-super@example.com")
        self.admin_1 = make_user(self.company, User.Role.ADMIN, "pub-admin-1@example.com")
        self.admin_2 = make_user(self.company, User.Role.ADMIN, "pub-admin-2@example.com")
        self.manager = authenticated_client(self.super)
        self.visitor = APIClient()

    def configure(self, *, unblock=True, **extra):
        body = {
            "lead_source": "Web Research",
            "assignment_mode": "SINGLE_OWNER",
            "single_owner_id": str(self.admin_1.id),
            **extra,
        }
        response = self.manager.patch(FORM, body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        token = response.data["public_token"]
        if unblock:
            unblocked = self.manager.post(FORM + "unblock/")
            self.assertEqual(unblocked.status_code, status.HTTP_200_OK, unblocked.content)
        return token

    def test_works_without_auth_and_with_invalid_bearer_token(self):
        token = self.configure()
        url = f"{PUBLIC}{token}/"

        got = self.visitor.get(url)
        self.assertEqual(got.status_code, status.HTTP_200_OK)
        self.assertEqual(
            got.json(),
            {"title": "Contact us", "company_name": "Public Co", "accepting_responses": True},
        )

        posted = self.visitor.post(url, payload(), format="json")
        self.assertEqual(posted.status_code, status.HTTP_201_CREATED, posted.content)
        self.assertEqual(posted.json(), {"detail": "Thanks, we've received your details."})

        stale = APIClient()
        stale.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(stale.get(url).status_code, status.HTTP_200_OK)
        self.assertEqual(
            stale.post(url, payload(email="two@example.com"), format="json").status_code,
            status.HTTP_201_CREATED,
        )

    def test_unknown_token_is_404(self):
        self.configure()
        url = f"{PUBLIC}does-not-exist/"
        self.assertEqual(self.visitor.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.visitor.post(url, payload(), format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_blocked_form_is_410_and_creates_no_lead(self):
        token = self.configure(unblock=False)  # new forms start blocked
        url = f"{PUBLIC}{token}/"

        got = self.visitor.get(url)
        self.assertEqual(got.status_code, status.HTTP_200_OK)
        self.assertFalse(got.json()["accepting_responses"])

        posted = self.visitor.post(url, payload(), format="json")
        self.assertEqual(posted.status_code, status.HTTP_410_GONE)
        self.assertEqual(posted.json(), {"detail": CLOSED})
        self.assertEqual(DjangoLeadModel.objects.count(), 0)

    def test_valid_submission_creates_lead_for_company_source_owner(self):
        token = self.configure()

        response = self.visitor.post(f"{PUBLIC}{token}/", payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        lead = DjangoLeadModel.objects.get()
        self.assertEqual(lead.company_id, self.company.id)
        self.assertEqual(lead.lead_source, "Web Research")
        self.assertEqual(lead.owner_id, self.admin_1.id)
        self.assertEqual(lead.description, MESSAGE)
        self.assertEqual(lead.name, "Visitor One")
        self.assertEqual(lead.email, "visitor@example.com")
        self.assertEqual(lead.phone, "9876543210")

        form = DjangoLeadFormModel.objects.get(company_id=self.company.id)
        self.assertEqual(form.submission_count, 1)
        self.assertIsNotNone(form.last_submission_at)

        # Unknown fields (e.g. an attempt to pick the company) are rejected.
        bad = self.visitor.post(
            f"{PUBLIC}{token}/", payload(company_id=str(self.company.id)), format="json"
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(DjangoLeadModel.objects.count(), 1)

    def test_rotation_alternates_between_two_owners(self):
        token = self.configure(
            assignment_mode="ROTATION",
            rotation_owner_ids=[str(self.admin_1.id), str(self.admin_2.id)],
            single_owner_id=None,
        )

        for index in range(4):
            response = self.visitor.post(
                f"{PUBLIC}{token}/",
                payload(email=f"v{index}@example.com"),
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        owners = list(
            DjangoLeadModel.objects.order_by("created_at").values_list("owner_id", flat=True)
        )
        self.assertEqual(
            owners,
            [self.admin_1.id, self.admin_2.id, self.admin_1.id, self.admin_2.id],
        )

    def test_more_posts_than_the_rate_is_429(self):
        token = self.configure()
        url = f"{PUBLIC}{token}/"
        rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "lead_capture_submit": "2/hour"}
        with override_settings(
            REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}
        ):
            for n in range(2):
                response = self.visitor.post(url, payload(email=f"t{n}@example.com"), format="json")
                self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

            throttled = self.visitor.post(url, payload(email="t3@example.com"), format="json")
            self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("detail", throttled.json())
            self.assertIn("Retry-After", throttled.headers)
            self.assertEqual(DjangoLeadModel.objects.count(), 2)
            # GET has its own scope and is not affected.
            self.assertEqual(self.visitor.get(url).status_code, status.HTTP_200_OK)

    @override_settings(LEAD_CAPTURE_DAILY_CAP=1)
    def test_daily_cap_reached_is_410_and_creates_no_lead(self):
        token = self.configure()
        url = f"{PUBLIC}{token}/"

        first = self.visitor.post(url, payload(), format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.content)

        second = self.visitor.post(url, payload(email="second@example.com"), format="json")
        self.assertEqual(second.status_code, status.HTTP_410_GONE)
        self.assertEqual(second.json(), {"detail": CLOSED})
        self.assertEqual(DjangoLeadModel.objects.count(), 1)

        form = DjangoLeadFormModel.objects.get(company_id=self.company.id)
        self.assertEqual(form.submission_count, 1)
        self.assertEqual(form.daily_submission_count, 1)

    @override_settings(LEAD_CAPTURE_DAILY_CAP=1)
    def test_daily_counter_resets_on_a_new_date(self):
        token = self.configure()
        url = f"{PUBLIC}{token}/"
        day_1, day_2 = date(2030, 1, 10), date(2030, 1, 11)

        with patch.object(timezone, "localdate", return_value=day_1):
            self.assertEqual(
                self.visitor.post(url, payload(), format="json").status_code,
                status.HTTP_201_CREATED,
            )
            self.assertEqual(
                self.visitor.post(url, payload(email="b@example.com"), format="json").status_code,
                status.HTTP_410_GONE,
            )

        with patch.object(timezone, "localdate", return_value=day_2):
            self.assertEqual(
                self.visitor.post(url, payload(email="c@example.com"), format="json").status_code,
                status.HTTP_201_CREATED,
            )

        form = DjangoLeadFormModel.objects.get(company_id=self.company.id)
        self.assertEqual(form.daily_submission_date, day_2)
        self.assertEqual(form.daily_submission_count, 1)
        self.assertEqual(form.submission_count, 2)
        self.assertEqual(DjangoLeadModel.objects.count(), 2)
