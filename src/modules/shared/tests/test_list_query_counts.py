from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.meetings.infrastructure.persistence.models import (
    DjangoMeetingModel,
)
from src.modules.shared.application.dto.list_query import ListQuery
from src.modules.shared.tests.tenancy.factories import make_company, make_user

ROWS = 5


class ListQueryCountTests(TestCase):
    """
    A list page costs a fixed number of queries, however many rows it has.

    The list repositories read only the columns the table shows
    (``.only()``) and join the owner / account / host names. Reading a column
    that was left out would silently load it with one extra query per row,
    so these tests fail if a list starts doing that.
    """

    def setUp(self):
        self.company = make_company("Query Count Co")
        self.owner = make_user(self.company, name="Owner One")
        self.now = timezone.now()

    def test_lead_list_is_two_queries(self):
        for i in range(ROWS):
            DjangoLeadModel.objects.create(
                company=self.company,
                owner=self.owner,
                name=f"Lead {i}",
                description="not shown in the list",
            )
        repository = DjangoLeadRepository(company_id=self.company.id)

        with self.assertNumQueries(2):  # count + page
            page = repository.get_all_with_owner(ListQuery())

        self.assertEqual(page.total, ROWS)
        lead, owner_name = page.results[0]
        self.assertEqual(owner_name, "Owner One")
        self.assertEqual(lead.owner_id, self.owner.id)
        self.assertIsNone(lead.description)  # not read by the list

    def test_contact_list_is_two_queries(self):
        account = self._account("Acme")
        for i in range(ROWS):
            DjangoContactModel.objects.create(
                company=self.company,
                account=account,
                contact_owner=self.owner,
                name=f"Contact {i}",
                description="not shown in the list",
                created_by=self.owner,
                modified_by=self.owner,
                created_at=self.now,
                updated_at=self.now,
            )
        repository = DjangoContactRepository(company_id=self.company.id)

        with self.assertNumQueries(2):  # count + page (next task is a subquery)
            page = repository.get_all_with_relations(ListQuery())

        self.assertEqual(page.total, ROWS)
        contact, account_name, owner_name, _, _ = page.results[0]
        self.assertEqual(account_name, "Acme")
        self.assertEqual(owner_name, "Owner One")
        self.assertIsNone(contact.description)  # not read by the list

    def test_account_list_is_two_queries(self):
        for i in range(ROWS):
            self._account(f"Account {i}")
        repository = DjangoAccountRepository(company_id=self.company.id)

        with self.assertNumQueries(2):  # count + page
            page = repository.get_all_with_owner(ListQuery())

        self.assertEqual(page.total, ROWS)
        account, owner_name = page.results[0]
        self.assertEqual(owner_name, "Owner One")
        self.assertIsNone(account.description)  # not read by the list

    def test_meeting_list_query_count_does_not_grow_with_rows(self):
        for i in range(ROWS):
            DjangoMeetingModel.objects.create(
                company=self.company,
                host=self.owner,
                created_by=self.owner,
                title=f"Meeting {i}",
                start_at=self.now,
                end_at=self.now + timedelta(hours=1),
            )
        repository = DjangoMeetingRepository(company_id=self.company.id)

        # count + page + related records + contact participants.
        with self.assertNumQueries(4):
            page = repository.get_all(ListQuery())

        self.assertEqual(page.total, ROWS)
        self.assertEqual(page.results[0].host_name, "Owner One")

    def _account(self, name):
        return DjangoAccountModel.objects.create(
            company=self.company,
            account_owner=self.owner,
            account_name=name,
            description="not shown in the list",
            created_by=self.owner,
            modified_by=self.owner,
            created_at=self.now,
            updated_at=self.now,
        )
