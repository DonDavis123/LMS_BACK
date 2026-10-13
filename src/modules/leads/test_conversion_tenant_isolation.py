import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User


def make_account(company, owner, name, **extra):
    now = timezone.now()
    return DjangoAccountModel.objects.create(
        company=company,
        account_owner=owner,
        account_name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


def make_contact(company, owner, name, account=None, **extra):
    now = timezone.now()
    return DjangoContactModel.objects.create(
        company=company,
        account=account,
        contact_owner=owner,
        name=name,
        created_by=owner,
        created_at=now,
        modified_by=owner,
        updated_at=now,
        **extra,
    )


def make_lead(company, owner, name, **extra):
    return DjangoLeadModel.objects.create(
        company=company, name=name, owner=owner, **extra,
    )


class ConversionTenantIsolationTests(APITestCase):
    """Company A and Company B, each with a SUPERADMIN and an ADMIN."""

    IDENTICAL = dict(
        email="same@example.com",
        phone="5550001",
        mobile_number="5559999",
        website="https://same.example.com",
        company_name="Shared Name",
    )

    def setUp(self):
        self.company_a = make_company("Company A", "company-a")
        self.company_b = make_company("Company B", "company-b")

        self.superadmin_a = make_user(
            self.company_a, User.Role.SUPERADMIN, "super-a@example.com",
        )
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "admin-a@example.com")
        self.superadmin_b = make_user(
            self.company_b, User.Role.SUPERADMIN, "super-b@example.com",
        )
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "admin-b@example.com")

        self.client_a = authenticated_client(self.superadmin_a)
        self.client_b = authenticated_client(self.superadmin_b)

        self.lead_a = make_lead(
            self.company_a, self.admin_a, "Same Person", **self.IDENTICAL,
        )
        self.lead_b = make_lead(
            self.company_b, self.admin_b, "Same Person", **self.IDENTICAL,
        )

        # Company B owns an account and a contact that match lead A on
        # name, email, phone, mobile, website and company name.
        self.b_account = make_account(
            self.company_b, self.admin_b, "Shared Name",
            website="https://same.example.com", phone="5550001",
        )
        self.b_contact = make_contact(
            self.company_b, self.admin_b, "Same Person", account=self.b_account,
            email="same@example.com", phone="5550001", mobile="5559999",
        )

    def check(self, client, lead_id):
        return client.get(f"/api/leads/{lead_id}/conversion-check/")

    def convert(self, client, lead_id, **payload):
        payload.setdefault("account_action", "create_new")
        payload.setdefault("contact_action", "create_new")
        return client.post(f"/api/leads/{lead_id}/convert/", payload, format="json")

    def assert_same_as_missing(self, foreign_response, missing_response):
        self.assertEqual(foreign_response.status_code, missing_response.status_code)
        self.assertEqual(foreign_response.data, missing_response.data)

    def test_converting_a_foreign_lead_is_rejected_like_a_missing_one(self):
        accounts = DjangoAccountModel.objects.count()
        contacts = DjangoContactModel.objects.count()

        foreign = self.convert(self.client_a, self.lead_b.id)
        missing = self.convert(self.client_a, uuid.uuid4())

        self.assertEqual(foreign.data, {"detail": "Lead not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertIn(
            foreign.status_code,
            {status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND},
        )

        self.lead_b.refresh_from_db()
        self.assertFalse(self.lead_b.is_converted)
        self.assertEqual(DjangoAccountModel.objects.count(), accounts)
        self.assertEqual(DjangoContactModel.objects.count(), contacts)

    def test_conversion_check_of_a_foreign_lead_is_rejected_like_a_missing_one(self):
        foreign = self.check(self.client_a, self.lead_b.id)
        missing = self.check(self.client_a, uuid.uuid4())

        self.assertEqual(foreign.data, {"detail": "Lead not found."})
        self.assert_same_as_missing(foreign, missing)

    def test_check_never_reports_matches_of_another_company(self):
        response = self.check(self.client_a, self.lead_a.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lead_id"], str(self.lead_a.id))
        self.assertEqual(response.data["accounts"], [])
        self.assertEqual(response.data["contacts"], [])

    def test_check_reports_only_matches_of_the_leads_company(self):
        a_account = make_account(
            self.company_a, self.admin_a, "Shared Name",
            website="https://same.example.com", phone="5550001",
        )
        a_contact = make_contact(
            self.company_a, self.admin_a, "Same Person", account=a_account,
            email="same@example.com", phone="5550001", mobile="5559999",
        )

        response = self.check(self.client_a, self.lead_a.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data["accounts"]], [str(a_account.id)])
        self.assertEqual([row["id"] for row in response.data["contacts"]], [str(a_contact.id)])

        response = self.check(self.client_b, self.lead_b.id)

        self.assertEqual(
            [row["id"] for row in response.data["accounts"]], [str(self.b_account.id)],
        )
        self.assertEqual(
            [row["id"] for row in response.data["contacts"]], [str(self.b_contact.id)],
        )

    def test_conversion_creates_account_and_contact_in_the_leads_company(self):
        response = self.convert(self.client_a, self.lead_a.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": "Lead converted successfully."})

        self.lead_a.refresh_from_db()
        self.assertTrue(self.lead_a.is_converted)

        account = DjangoAccountModel.objects.get(
            company=self.company_a, account_name="Shared Name",
        )
        contact = DjangoContactModel.objects.get(
            company=self.company_a, name="Same Person",
        )
        self.assertEqual(account.company_id, self.company_a.id)
        self.assertEqual(contact.company_id, self.company_a.id)
        self.assertEqual(contact.account_id, account.id)

        # Nothing was created for, or changed in, the other company.
        self.assertEqual(
            DjangoAccountModel.objects.filter(company=self.company_b).count(), 1,
        )
        self.assertEqual(
            DjangoContactModel.objects.filter(company=self.company_b).count(), 1,
        )
        self.b_contact.refresh_from_db()
        self.assertEqual(self.b_contact.account_id, self.b_account.id)
        self.lead_b.refresh_from_db()
        self.assertFalse(self.lead_b.is_converted)

    def test_conversion_cannot_use_an_account_of_another_company(self):
        foreign = self.convert(
            self.client_a, self.lead_a.id,
            account_action="use_existing", account_id=str(self.b_account.id),
        )
        missing = self.convert(
            self.client_a, self.lead_a.id,
            account_action="use_existing", account_id=str(uuid.uuid4()),
        )

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Selected Account not found."})
        self.assert_same_as_missing(foreign, missing)

        self.lead_a.refresh_from_db()
        self.assertFalse(self.lead_a.is_converted)
        self.assertEqual(
            DjangoContactModel.objects.filter(company=self.company_a).count(), 0,
        )

    def test_conversion_cannot_use_a_contact_of_another_company(self):
        foreign = self.convert(
            self.client_a, self.lead_a.id,
            account_action="create_new",
            contact_action="use_existing", contact_id=str(self.b_contact.id),
        )
        missing = self.convert(
            self.client_a, self.lead_a.id,
            account_action="create_new",
            contact_action="use_existing", contact_id=str(uuid.uuid4()),
        )

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Selected Contact not found."})
        self.assert_same_as_missing(foreign, missing)

        self.lead_a.refresh_from_db()
        self.assertFalse(self.lead_a.is_converted)
        # The failed conversion rolled back: no account was left behind.
        self.assertEqual(
            DjangoAccountModel.objects.filter(company=self.company_a).count(), 0,
        )
        self.b_contact.refresh_from_db()
        self.assertEqual(self.b_contact.account_id, self.b_account.id)

    def test_conversion_can_use_existing_records_of_its_own_company(self):
        a_account = make_account(self.company_a, self.admin_a, "Own Account")
        a_contact = make_contact(self.company_a, self.admin_a, "Own Contact")

        response = self.convert(
            self.client_a, self.lead_a.id,
            account_action="use_existing", account_id=str(a_account.id),
            contact_action="use_existing", contact_id=str(a_contact.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lead_a.refresh_from_db()
        self.assertTrue(self.lead_a.is_converted)
        a_contact.refresh_from_db()
        self.assertEqual(a_contact.account_id, a_account.id)
