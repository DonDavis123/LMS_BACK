"""Stored lead summary: ``GET`` / ``POST /api/leads/<id>/summary/``.

Gemini is never called: ``GeminiLeadSummaryGenerator`` is patched.
"""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.leads.application.dto.lead_summary import LeadSummaryResult
from src.modules.leads.application.interfaces.lead_summary_generator import (
    LeadSummaryError,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_summary_model import (
    DjangoLeadSummaryModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)

GENERATOR = (
    "src.modules.leads.infrastructure.summary."
    "gemini_lead_summary_generator.GeminiLeadSummaryGenerator"
)


def result(headline):
    return LeadSummaryResult(
        headline=headline,
        key_points=["Asked for a quote"],
        next_steps=["Send the quote"],
        model_name="gemini-test",
    )


class LeadSummaryStorageTests(APITestCase):
    def setUp(self):
        self.company = make_company("Acme")
        self.user = make_user(self.company)
        self.lead = DjangoLeadModel.objects.create(
            company=self.company, name="Asha Nair", owner=self.user,
        )
        self.client = authenticated_client(self.user)
        self.url = f"/api/leads/{self.lead.id}/summary/"

        configured = patch(f"{GENERATOR}.is_configured", return_value=True)
        configured.start()
        self.addCleanup(configured.stop)

    def generate(self, headline="Warm lead"):
        with patch(f"{GENERATOR}.generate", return_value=result(headline)):
            return self.client.post(self.url, {}, format="json")

    def test_get_is_empty_before_the_first_summary(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_post_stores_the_summary_and_get_returns_it(self):
        posted = self.generate("Warm lead")
        self.assertEqual(posted.status_code, status.HTTP_200_OK)

        fetched = self.client.get(self.url)

        self.assertEqual(fetched.status_code, status.HTTP_200_OK)
        self.assertEqual(fetched.data["headline"], "Warm lead")
        self.assertEqual(fetched.data["key_points"], ["Asked for a quote"])
        self.assertEqual(fetched.data["next_steps"], ["Send the quote"])
        self.assertEqual(fetched.data["generated_at"], posted.data["generated_at"])
        self.assertEqual(DjangoLeadSummaryModel.objects.count(), 1)

    def test_refresh_permanently_replaces_the_old_summary(self):
        self.generate("Old summary")
        old_id = DjangoLeadSummaryModel.objects.get(lead=self.lead).id

        self.generate("New summary")

        rows = DjangoLeadSummaryModel.objects.filter(lead=self.lead)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().headline, "New summary")
        # A new row, not an edit of the old one: the old record is gone.
        self.assertNotEqual(rows.get().id, old_id)
        self.assertFalse(DjangoLeadSummaryModel.objects.filter(id=old_id).exists())
        self.assertEqual(self.client.get(self.url).data["headline"], "New summary")

    def test_failed_refresh_keeps_the_old_summary(self):
        self.generate("Old summary")

        with patch(f"{GENERATOR}.generate", side_effect=LeadSummaryError("Busy.")):
            response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(self.client.get(self.url).data["headline"], "Old summary")
        self.assertEqual(DjangoLeadSummaryModel.objects.count(), 1)

    def test_other_company_cannot_read_or_replace_a_summary(self):
        self.generate("Acme summary")
        stranger = authenticated_client(make_user(make_company("Other")))

        self.assertEqual(stranger.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        with patch(f"{GENERATOR}.generate", return_value=result("Hijacked")):
            posted = stranger.post(self.url, {}, format="json")
        self.assertEqual(posted.status_code, status.HTTP_404_NOT_FOUND)

        self.assertEqual(self.client.get(self.url).data["headline"], "Acme summary")

    def test_each_lead_keeps_its_own_summary(self):
        other = DjangoLeadModel.objects.create(
            company=self.company, name="Ravi", owner=self.user,
        )
        self.generate("First lead")
        with patch(f"{GENERATOR}.generate", return_value=result("Second lead")):
            self.client.post(f"/api/leads/{other.id}/summary/", {}, format="json")

        self.assertEqual(DjangoLeadSummaryModel.objects.count(), 2)
        self.assertEqual(self.client.get(self.url).data["headline"], "First lead")

    def test_requires_login(self):
        from rest_framework.test import APIClient

        self.assertEqual(
            APIClient().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )
