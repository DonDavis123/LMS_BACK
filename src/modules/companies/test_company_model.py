import dataclasses

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from src.modules.companies.domain.entities.company import Company
from src.modules.companies.domain.entities.company_status import CompanyStatus
from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.users.infrastructure.persistence.models import User


class CompanyModelTests(TestCase):

    def test_status_defaults_to_onboarding(self):
        company = DjangoCompanyModel.objects.create(name="Acme", slug="acme")
        company.refresh_from_db()

        self.assertEqual(company.status, DjangoCompanyModel.Status.ONBOARDING)
        self.assertEqual(company.status, CompanyStatus.ONBOARDING.value)
        self.assertEqual(company.status_reason, "")
        self.assertIsNone(company.status_changed_at)
        self.assertIsNone(company.status_changed_by)
        self.assertIsNone(company.created_by)
        self.assertIsNotNone(company.created_at)
        self.assertIsNotNone(company.updated_at)

    def test_slug_is_unique_ignoring_case(self):
        DjangoCompanyModel.objects.create(name="Acme", slug="acme")

        for duplicate in ("acme", "ACME", "Acme"):
            with self.subTest(slug=duplicate):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    DjangoCompanyModel.objects.create(
                        name="Another Acme",
                        slug=duplicate,
                    )

        self.assertEqual(DjangoCompanyModel.objects.count(), 1)

    def test_different_slugs_can_share_a_name(self):
        DjangoCompanyModel.objects.create(name="Acme", slug="acme")
        DjangoCompanyModel.objects.create(name="Acme", slug="acme-2")

        self.assertEqual(DjangoCompanyModel.objects.count(), 2)

    def test_slug_validation(self):
        slug_field = DjangoCompanyModel._meta.get_field("slug")

        for invalid in ("Acme Corp", "acme/corp", "acme.corp", "acme!", "", "a" * 101):
            with self.subTest(slug=invalid):
                with self.assertRaises(ValidationError):
                    slug_field.clean(invalid, None)

        for valid in ("acme", "acme-corp", "acme_corp_2", "ACME", "a" * 100):
            with self.subTest(slug=valid):
                self.assertEqual(slug_field.clean(valid, None), valid)

    def test_full_clean_rejects_invalid_slug(self):
        company = DjangoCompanyModel(name="Acme", slug="not a slug")

        with self.assertRaises(ValidationError) as context:
            company.full_clean()

        self.assertIn("slug", context.exception.message_dict)

    def test_companies_are_ordered_by_name(self):
        DjangoCompanyModel.objects.create(name="Zeta", slug="zeta")
        DjangoCompanyModel.objects.create(name="Alpha", slug="alpha")

        self.assertEqual(
            list(DjangoCompanyModel.objects.values_list("name", flat=True)),
            ["Alpha", "Zeta"],
        )

    def test_audit_users_are_set_null_when_the_user_is_removed(self):
        creator = User.objects.create_user(
            email="creator@example.com",
            password="creator-password",
            name="Creator",
            role=User.Role.ADMIN,
        )
        company = DjangoCompanyModel.objects.create(
            name="Acme",
            slug="acme",
            created_by=creator,
            status_changed_by=creator,
        )

        creator.delete()
        company.refresh_from_db()

        self.assertIsNone(company.created_by)
        self.assertIsNone(company.status_changed_by)


class CompanyDomainTests(SimpleTestCase):

    def test_status_values_match_the_model_choices(self):
        self.assertEqual(
            {status.value for status in CompanyStatus},
            {value for value, _ in DjangoCompanyModel.Status.choices},
        )

    def test_entity_mirrors_the_model_fields(self):
        entity_fields = {field.name for field in dataclasses.fields(Company)}
        model_fields = {
            field.attname for field in DjangoCompanyModel._meta.concrete_fields
        }

        self.assertEqual(entity_fields, model_fields)
