"""Helpers shared by the deals tests (not a test module itself)."""
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.deals.infrastructure.persistence.models import DjangoDealModel
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

URL = "/api/deals/"


def make_account(company, owner, name="Acme", **extra):
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


def make_contact(company, owner, name="Jane Doe", account=None, **extra):
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


def make_lead(company, owner, name="Lead Person", **extra):
    return DjangoLeadModel.objects.create(
        company=company, name=name, owner=owner, **extra,
    )


def make_deal(company, owner, account=None, contact=None, **extra):
    """Create a deal row directly (bypasses the API)."""
    extra.setdefault("name", "Seeded Deal")
    extra.setdefault("amount", Decimal("1000.00"))
    return DjangoDealModel.objects.create(
        company=company,
        owner=owner,
        created_by=owner,
        account=account,
        contact=contact,
        **extra,
    )


class DealApiTestBase(APITestCase):
    def setUp(self):
        self.company = make_company("Company A", "company-a")
        self.admin = make_user(self.company, User.Role.ADMIN, "admin@a.example.com", name="Admin A")
        self.superadmin = make_user(self.company, User.Role.SUPERADMIN, "super@a.example.com", name="Super A")
        self.client = authenticated_client(self.superadmin)

        self.account = make_account(self.company, self.admin, "Acme Corp")
        self.contact = make_contact(self.company, self.admin, "Jane Doe", account=self.account)

    def payload(self, **overrides):
        data = {
            "name": "Big Deal",
            "amount": "100000.00",
            "owner_id": str(self.admin.id),
            "account_id": str(self.account.id),
        }
        data.update(overrides)
        return data

    def create(self, **overrides):
        return self.client.post(URL, self.payload(**overrides), format="json")
