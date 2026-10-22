import re
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.db import connection
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_model import (
    DjangoLeadFormModel,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_repository import (
    DjangoLeadFormRepository,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

FORM = "/api/lead-capture/form/"
BLOCK = FORM + "block/"
UNBLOCK = FORM + "unblock/"
REGENERATE = FORM + "regenerate-link/"
PLATFORM_COMPANIES = "/api/platform/companies/"


class LeadFormTestCase(APITestCase):
    """Company A (SUPERADMIN + ADMIN + SALES_EXECUTIVE) and Company B."""

    def setUp(self):
        self.company_a = make_company("Lead A", "lead-a")
        self.company_b = make_company("Lead B", "lead-b")
        # make_company() skips the use case, so the form is made lazily on
        # first access (the repository's safety net).
        self.super_a = make_user(self.company_a, User.Role.SUPERADMIN, "lc-super-a@example.com")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "lc-admin-a@example.com")
        self.sales_a = make_user(self.company_a, User.Role.SALES_EXECUTIVE, "lc-sales-a@example.com")
        self.super_b = make_user(self.company_b, User.Role.SUPERADMIN, "lc-super-b@example.com")

        self.sa = authenticated_client(self.super_a)
        self.sb = authenticated_client(self.super_b)

    def configure(self, **extra):
        payload = {
            "lead_source": "Web Research",
            "assignment_mode": "SINGLE_OWNER",
            "single_owner_id": str(self.admin_a.id),
            **extra,
        }
        response = self.sa.patch(FORM, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return response.data


class ManagementApiTests(LeadFormTestCase):
    def test_new_form_is_blocked_and_not_configured(self):
        response = self.sa.get(FORM)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["title"], "Contact us")
        self.assertFalse(data["is_active"])
        self.assertFalse(data["is_configured"])
        self.assertFalse(data["needs_attention"])
        self.assertIsNone(data["lead_source"])
        self.assertIsNone(data["single_owner"])
        self.assertEqual(data["rotation_owners"], [])
        self.assertEqual(data["submission_count"], 0)
        self.assertTrue(data["public_token"])

    @override_settings(FRONTEND_URL="https://app.example.com/")
    def test_public_url_uses_frontend_url_without_double_slash(self):
        data = self.sa.get(FORM).data
        self.assertEqual(
            data["public_url"], f"https://app.example.com/lead/{data['public_token']}"
        )

    def test_only_company_superadmin_can_see_the_form_or_token(self):
        for user in (self.admin_a, self.sales_a):
            response = authenticated_client(user).get(FORM)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn("public_token", response.content.decode())

        self.assertEqual(self.client.get(FORM).status_code, status.HTTP_401_UNAUTHORIZED)

        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "lc-platform@example.com")
        self.assertEqual(
            authenticated_client(platform).get(FORM).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_each_company_only_sees_its_own_form(self):
        token_a = self.sa.get(FORM).data["public_token"]
        token_b = self.sb.get(FORM).data["public_token"]
        self.assertNotEqual(token_a, token_b)

        # B regenerating its link or blocking never touches A's form.
        self.sb.post(REGENERATE)
        self.assertEqual(self.sa.get(FORM).data["public_token"], token_a)

    def test_configure_then_unblock(self):
        data = self.configure()
        self.assertTrue(data["is_configured"])
        self.assertFalse(data["is_active"])
        self.assertEqual(data["single_owner"]["id"], str(self.admin_a.id))

        response = self.sa.post(UNBLOCK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

        response = self.sa.post(BLOCK)
        self.assertFalse(response.data["is_active"])

    def test_unblock_is_rejected_while_not_configured(self):
        response = self.sa.post(UNBLOCK)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("before unblocking", response.data["detail"])
        self.assertFalse(self.sa.get(FORM).data["is_active"])

        # A source alone is still not enough.
        self.sa.patch(FORM, {"lead_source": "Web Research"}, format="json")
        self.assertEqual(self.sa.post(UNBLOCK).status_code, status.HTTP_400_BAD_REQUEST)

    def test_regenerate_link_replaces_the_token(self):
        old = self.sa.get(FORM).data["public_token"]
        new = self.sa.post(REGENERATE).data["public_token"]

        self.assertNotEqual(old, new)
        self.assertFalse(DjangoLeadFormModel.objects.filter(public_token=old).exists())
        self.assertTrue(DjangoLeadFormModel.objects.filter(public_token=new).exists())
        self.assertRegex(new, re.compile(r"^[A-Za-z0-9_-]{32}$"))

    def test_rotation_keeps_the_given_order(self):
        data = self.configure(
            assignment_mode="ROTATION",
            rotation_owner_ids=[str(self.admin_a.id), str(self.super_a.id)],
        )
        self.assertEqual(
            [(o["id"], o["position"]) for o in data["rotation_owners"]],
            [(str(self.admin_a.id), 0), (str(self.super_a.id), 1)],
        )

        data = self.sa.patch(
            FORM,
            {"rotation_owner_ids": [str(self.super_a.id), str(self.admin_a.id)]},
            format="json",
        ).data
        self.assertEqual(
            [o["id"] for o in data["rotation_owners"]],
            [str(self.super_a.id), str(self.admin_a.id)],
        )


class ValidationTests(LeadFormTestCase):
    def patch(self, payload):
        return self.sa.patch(FORM, payload, format="json")

    def test_unknown_lead_source_is_rejected(self):
        response = self.patch({"lead_source": "Carrier Pigeon"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not a valid option", response.data["detail"])

    def test_owner_must_be_eligible_and_in_the_same_company(self):
        for bad in (
            self.super_b.id,  # other company
            self.sales_a.id,  # role cannot own leads
            "00000000-0000-0000-0000-000000000000",  # unknown
        ):
            response = self.patch(
                {"assignment_mode": "SINGLE_OWNER", "single_owner_id": str(bad)}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, bad)

        inactive = make_user(self.company_a, User.Role.ADMIN, "lc-off@example.com", is_active=False)
        response = self.patch(
            {"assignment_mode": "SINGLE_OWNER", "single_owner_id": str(inactive.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mode_requirements(self):
        self.assertEqual(
            self.patch({"assignment_mode": "SINGLE_OWNER"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.patch({"assignment_mode": "ROTATION"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.patch({"rotation_owner_ids": []}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        duplicate = str(self.admin_a.id)
        self.assertEqual(
            self.patch(
                {"assignment_mode": "ROTATION", "rotation_owner_ids": [duplicate, duplicate]}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unknown_fields_and_empty_body_are_rejected(self):
        for payload in ({"is_active": True}, {"public_token": "x"}, {"title": "A", "foo": 1}, {}):
            self.assertEqual(
                self.patch(payload).status_code, status.HTTP_400_BAD_REQUEST, payload
            )

    def test_failed_patch_changes_nothing(self):
        self.configure()
        before = self.sa.get(FORM).data
        self.patch({"title": "New title", "lead_source": "Carrier Pigeon"})
        self.assertEqual(self.sa.get(FORM).data["title"], before["title"])

    def test_edit_that_unconfigures_a_live_form_is_rejected(self):
        self.configure()
        self.sa.post(UNBLOCK)

        response = self.patch({"lead_source": None})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Block the form first", response.data["detail"])
        self.assertTrue(self.sa.get(FORM).data["is_configured"])

        # Harmless edits, and edits that keep it configured, still work.
        self.assertEqual(self.patch({"title": "Talk to us"}).status_code, status.HTTP_200_OK)
        self.assertEqual(self.patch({"lead_source": "Partner"}).status_code, status.HTTP_200_OK)


class OwnerLifecycleTests(LeadFormTestCase):
    def test_deactivated_owner_flags_needs_attention_without_breaking(self):
        self.configure()
        self.sa.post(UNBLOCK)

        self.admin_a.is_active = False
        self.admin_a.save()

        response = self.sa.get(FORM)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_configured"])
        self.assertTrue(response.data["needs_attention"])

        # It can be blocked, and cannot be unblocked until fixed.
        self.assertEqual(self.sa.post(BLOCK).status_code, status.HTTP_200_OK)
        self.assertEqual(self.sa.post(UNBLOCK).status_code, status.HTTP_400_BAD_REQUEST)

    def test_rotation_survives_losing_one_owner(self):
        self.configure(
            assignment_mode="ROTATION",
            rotation_owner_ids=[str(self.admin_a.id), str(self.super_a.id)],
        )
        self.sa.post(UNBLOCK)

        from django.utils import timezone

        self.admin_a.deleted_at = timezone.now()
        self.admin_a.save()

        data = self.sa.get(FORM).data
        self.assertTrue(data["is_configured"])
        self.assertFalse(data["needs_attention"])


class CompanyCreationTests(APITestCase):
    def setUp(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "lc-pa@example.com")
        self.client = authenticated_client(platform)
        self.payload = {
            "company_name": "Form Co",
            "admin_name": "Fiona",
            "admin_email": "fiona@formco.example.com",
            "admin_password": "s3cret-pass",
        }

    def test_new_company_gets_a_blocked_unconfigured_form(self):
        response = self.client.post(PLATFORM_COMPANIES, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        form = DjangoLeadFormModel.objects.get(company_id=response.data["company"]["id"])
        self.assertFalse(form.is_active)
        self.assertEqual(form.lead_source, "")
        self.assertIsNone(form.single_owner_id)
        self.assertGreaterEqual(len(form.public_token), 32)

    def test_company_is_rolled_back_when_the_form_cannot_be_created(self):
        with mock.patch.object(
            DjangoLeadFormRepository, "create_default", side_effect=RuntimeError("boom")
        ):
            response = self.client.post(PLATFORM_COMPANIES, self.payload, format="json")

        self.assertGreaterEqual(response.status_code, 400)
        self.assertFalse(DjangoCompanyModel.objects.filter(name="Form Co").exists())
        self.assertFalse(User.objects.filter(email="fiona@formco.example.com").exists())


class BackfillMigrationTests(APITestCase):
    def run_backfill(self):
        from importlib import import_module

        migration = import_module(
            "src.modules.lead_capture.migrations.0002_backfill_lead_forms"
        )
        migration.backfill_lead_forms(apps, SimpleNamespace(connection=connection))
        return migration

    def test_backfill_is_idempotent_and_gives_each_company_its_own_token(self):
        companies = [make_company(f"Old {i}", f"old-{i}") for i in range(3)]
        DjangoLeadFormModel.objects.all().delete()

        self.run_backfill()
        first = dict(DjangoLeadFormModel.objects.values_list("company_id", "public_token"))
        self.run_backfill()  # second run changes nothing
        second = dict(DjangoLeadFormModel.objects.values_list("company_id", "public_token"))

        self.assertEqual(first, second)
        self.assertEqual(set(first), {c.id for c in companies})
        self.assertEqual(len(set(first.values())), len(companies))
        self.assertFalse(DjangoLeadFormModel.objects.filter(is_active=True).exists())

    def test_backfill_leaves_existing_forms_alone_and_reverse_keeps_configured_ones(self):
        configured = make_company("Kept", "kept")
        untouched = make_company("Untouched", "untouched")
        DjangoLeadFormModel.objects.all().delete()
        self.run_backfill()
        DjangoLeadFormModel.objects.filter(company=configured).update(lead_source="Partner")

        migration = self.run_backfill()  # does not duplicate or reset
        self.assertEqual(
            DjangoLeadFormModel.objects.get(company=configured).lead_source, "Partner"
        )

        migration.remove_untouched_lead_forms(apps, SimpleNamespace(connection=connection))
        self.assertTrue(DjangoLeadFormModel.objects.filter(company=configured).exists())
        self.assertFalse(DjangoLeadFormModel.objects.filter(company=untouched).exists())
