import json
import uuid
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.domain.entities.contact import Contact
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
    token_client,
)
from src.modules.tasks.infrastructure.persistence.models import DjangoTaskModel
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


def make_task(owner, contact, subject, due_date, task_status):
    # Deliberately created WITHOUT a company: tasks are not scoped yet and
    # the contact list must still show them.
    return DjangoTaskModel.objects.create(
        subject=subject,
        owner=owner,
        created_by=owner,
        contact=contact,
        due_date=due_date,
        status=task_status,
    )


class TwoCompaniesContactsTestCase(APITestCase):
    """Company A and Company B, each with a SUPERADMIN and an ADMIN."""

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

        self.account_a = make_account(self.company_a, self.admin_a, "Acme A")
        self.account_b = make_account(self.company_b, self.admin_b, "Acme B")

        # Both companies deliberately own a contact with identical data.
        self.a_ann = make_contact(
            self.company_a, self.admin_a, "Ann Alpha", account=self.account_a,
            email="ann@example.com",
        )
        self.a_same = make_contact(
            self.company_a, self.superadmin_a, "Same Person",
            email="same@example.com", phone="5550001", mobile="5559999",
        )
        self.a_carl = make_contact(
            self.company_a, self.admin_a, "Carl Alpha", email="carl@example.com",
        )

        self.b_bob = make_contact(
            self.company_b, self.admin_b, "Bob Beta", account=self.account_b,
            email="bob@example.com",
        )
        self.b_same = make_contact(
            self.company_b, self.superadmin_b, "Same Person",
            email="same@example.com", phone="5550001", mobile="5559999",
        )
        self.b_dan = make_contact(
            self.company_b, self.admin_b, "Dan Beta", email="dan@example.com",
        )

        self.all_a_ids = {str(self.a_ann.id), str(self.a_same.id), str(self.a_carl.id)}
        self.all_b_ids = {str(self.b_bob.id), str(self.b_same.id), str(self.b_dan.id)}

    @staticmethod
    def filters(*conditions):
        return json.dumps(list(conditions))

    @staticmethod
    def ids(response):
        return {row["id"] for row in response.data["results"]}

    @staticmethod
    def names(response):
        return [row["name"] for row in response.data["results"]]

    def assert_same_as_missing(self, foreign_response, missing_response):
        """A foreign record must be indistinguishable from a missing one."""
        self.assertEqual(foreign_response.status_code, missing_response.status_code)
        self.assertEqual(foreign_response.data, missing_response.data)

    def patch(self, client, contact_id, **payload):
        return client.patch(
            f"/api/contacts/{contact_id}/update/", payload, format="json",
        )


class ContactListIsolationTests(TwoCompaniesContactsTestCase):

    def test_list_returns_only_own_contacts(self):
        response = self.client_a.get("/api/contacts/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), self.all_a_ids)
        self.assertEqual(response.data["pagination"]["total"], 3)

        response = self.client_b.get("/api/contacts/", {"page_size": 50})

        self.assertEqual(self.ids(response), self.all_b_ids)
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_list_works_with_real_jwt_authentication(self):
        response = token_client(self.superadmin_a).get("/api/contacts/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), self.all_a_ids)

    def test_search_only_returns_own_contacts(self):
        response = self.client_a.get("/api/contacts/", {"search": "Same"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {str(self.a_same.id)})

        response = self.client_a.get("/api/contacts/", {"search": "same@example"})
        self.assertEqual(self.ids(response), {str(self.a_same.id)})

        for term in ("Beta", "bob@example.com", "Dan"):
            with self.subTest(term=term):
                response = self.client_a.get("/api/contacts/", {"search": term})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["results"], [])
                self.assertEqual(response.data["pagination"]["total"], 0)

    def test_filters_only_return_own_contacts(self):
        response = self.client_a.get("/api/contacts/", {
            "filters": self.filters(
                {"field": "name", "operator": "equals", "value": "Same Person"},
            ),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {str(self.a_same.id)})

        response = self.client_a.get("/api/contacts/", {
            "filters": self.filters(
                {"field": "email", "operator": "contains", "value": "example.com"},
            ),
        })
        self.assertEqual(self.ids(response), self.all_a_ids)

        response = self.client_a.get("/api/contacts/", {
            "filters": self.filters(
                {"field": "name", "operator": "not_equals", "value": "Same Person"},
            ),
        })
        self.assertEqual(
            self.ids(response), {str(self.a_ann.id), str(self.a_carl.id)},
        )

        response = self.client_a.get("/api/contacts/", {
            "filters": self.filters(
                {"field": "account_name", "operator": "contains", "value": "Acme"},
            ),
        })
        self.assertEqual(self.ids(response), {str(self.a_ann.id)})

        for field, value in (
            ("contact_owner", str(self.admin_b.id)),
            ("account", str(self.account_b.id)),
        ):
            with self.subTest(field=field):
                response = self.client_a.get("/api/contacts/", {
                    "filters": self.filters(
                        {"field": field, "operator": "equals", "value": value},
                    ),
                })
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["results"], [])
                self.assertEqual(response.data["pagination"]["total"], 0)

    def test_sorting_only_returns_own_contacts(self):
        response = self.client_a.get("/api/contacts/", {
            "sort_by": "name", "sort_direction": "asc", "page_size": 50,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names(response), ["Ann Alpha", "Carl Alpha", "Same Person"])

        response = self.client_a.get("/api/contacts/", {
            "sort_by": "name", "sort_direction": "desc", "page_size": 50,
        })
        self.assertEqual(self.names(response), ["Same Person", "Carl Alpha", "Ann Alpha"])

        response = self.client_a.get("/api/contacts/", {
            "sort_by": "account", "sort_direction": "asc", "page_size": 50,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), self.all_a_ids)

    def test_pagination_only_returns_own_contacts(self):
        seen = set()
        for page in (1, 2):
            response = self.client_a.get("/api/contacts/", {"page": page, "page_size": 2})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["pagination"]["total"], 3)
            self.assertEqual(response.data["pagination"]["total_pages"], 2)
            seen |= self.ids(response)

        self.assertEqual(seen, self.all_a_ids)

        response = self.client_a.get("/api/contacts/", {"page": 3, "page_size": 2})
        self.assertEqual(response.data["results"], [])

    def test_next_task_columns_still_work(self):
        make_task(self.admin_a, self.a_ann, "Done", date(2026, 1, 1), "Completed")
        make_task(self.admin_a, self.a_ann, "Later", date(2027, 1, 15), "Not Started")
        make_task(self.admin_a, self.a_ann, "Next", date(2026, 12, 31), "In Progress")
        # A task of the other company's contact must never show up here.
        make_task(self.admin_b, self.b_same, "Foreign", date(2020, 1, 1), "Not Started")

        response = self.client_a.get("/api/contacts/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["id"]: row for row in response.data["results"]}

        self.assertEqual(rows[str(self.a_ann.id)]["next_task_due_date"], "2026-12-31")
        self.assertEqual(rows[str(self.a_ann.id)]["next_task_status"], "In Progress")
        self.assertIsNone(rows[str(self.a_same.id)]["next_task_due_date"])
        self.assertIsNone(rows[str(self.a_same.id)]["next_task_status"])

        response = self.client_b.get("/api/contacts/", {"page_size": 50})
        rows = {row["id"]: row for row in response.data["results"]}
        self.assertEqual(rows[str(self.b_same.id)]["next_task_due_date"], "2020-01-01")
        self.assertEqual(rows[str(self.b_same.id)]["next_task_status"], "Not Started")

    def test_soft_deleted_contacts_stay_hidden_inside_the_company(self):
        self.a_carl.is_deleted = True
        self.a_carl.save(update_fields=["is_deleted"])

        response = self.client_a.get("/api/contacts/", {"page_size": 50})

        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertNotIn(str(self.a_carl.id), self.ids(response))

    def test_platform_superadmin_cannot_reach_company_contacts(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "platform@example.com")
        client = authenticated_client(platform)

        self.assertEqual(
            client.get("/api/contacts/").status_code, status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            client.post(
                "/api/contacts/create/", {"name": "Nope"}, format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            client.get(f"/api/contacts/{self.a_ann.id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )


class ContactDetailIsolationTests(TwoCompaniesContactsTestCase):

    def test_detail_of_own_contact_is_returned(self):
        response = self.client_a.get(f"/api/contacts/{self.a_ann.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.a_ann.id))
        self.assertEqual(response.data["account_name"], "Acme A")

    def test_detail_of_foreign_contact_is_404_like_a_missing_one(self):
        foreign = self.client_a.get(f"/api/contacts/{self.b_bob.id}/")
        missing = self.client_a.get(f"/api/contacts/{uuid.uuid4()}/")

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.data, {"detail": "Contact not found."})
        self.assert_same_as_missing(foreign, missing)


class ContactUpdateIsolationTests(TwoCompaniesContactsTestCase):

    def test_update_of_own_contact_works(self):
        response = self.patch(self.client_a, self.a_ann.id, name="Ann Renamed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.name, "Ann Renamed")
        self.assertEqual(self.a_ann.company_id, self.company_a.id)

    def test_update_of_foreign_contact_is_rejected_and_changes_nothing(self):
        before = DjangoContactModel.objects.get(id=self.b_bob.id)

        foreign = self.patch(self.client_a, self.b_bob.id, name="Hijacked")
        missing = self.patch(self.client_a, uuid.uuid4(), name="Hijacked")

        # Same response as for a record that does not exist.
        self.assertEqual(foreign.data, {"detail": "Contact not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertIn(
            foreign.status_code,
            {status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND},
        )

        after = DjangoContactModel.objects.get(id=self.b_bob.id)
        self.assertEqual(after.name, "Bob Beta")
        self.assertEqual(after.company_id, self.company_b.id)
        self.assertEqual(after.account_id, self.account_b.id)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(after.modified_by_id, before.modified_by_id)

    def test_update_moving_contact_to_a_foreign_account_is_rejected(self):
        foreign = self.patch(self.client_a, self.a_ann.id, account_id=str(self.account_b.id))
        missing = self.patch(self.client_a, self.a_ann.id, account_id=str(uuid.uuid4()))

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Selected Account not found."})
        self.assert_same_as_missing(foreign, missing)

        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.account_id, self.account_a.id)

    def test_update_with_foreign_owner_is_rejected(self):
        foreign = self.patch(
            self.client_a, self.a_ann.id, contact_owner_id=str(self.admin_b.id),
        )
        missing = self.patch(
            self.client_a, self.a_ann.id, contact_owner_id=str(uuid.uuid4()),
        )

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Contact owner does not exist."})
        self.assert_same_as_missing(foreign, missing)

        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.contact_owner_id, self.admin_a.id)

    def test_update_with_own_company_account_and_owner_is_allowed(self):
        other_account = make_account(self.company_a, self.admin_a, "Another A")

        response = self.patch(
            self.client_a,
            self.a_ann.id,
            account_id=str(other_account.id),
            contact_owner_id=str(self.superadmin_a.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.account_id, other_account.id)
        self.assertEqual(self.a_ann.contact_owner_id, self.superadmin_a.id)

    def test_update_reporting_to_a_foreign_contact_is_rejected(self):
        foreign = self.patch(
            self.client_a, self.a_ann.id, reporting_to_id=str(self.b_bob.id),
        )
        missing = self.patch(
            self.client_a, self.a_ann.id, reporting_to_id=str(uuid.uuid4()),
        )

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Reporting contact not found."})
        self.assert_same_as_missing(foreign, missing)

        self.a_ann.refresh_from_db()
        self.assertIsNone(self.a_ann.reporting_to_id)

    def test_update_reporting_to_an_own_contact_is_allowed(self):
        response = self.patch(
            self.client_a, self.a_ann.id, reporting_to_id=str(self.a_carl.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.reporting_to_id, self.a_carl.id)

    def test_company_in_the_body_is_ignored(self):
        response = self.patch(
            self.client_a,
            self.a_ann.id,
            name="Ann Renamed",
            company=str(self.company_b.id),
            company_id=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_ann.refresh_from_db()
        self.assertEqual(self.a_ann.company_id, self.company_a.id)


class ContactDeleteIsolationTests(TwoCompaniesContactsTestCase):

    def test_delete_of_own_contact_works(self):
        response = self.client_a.delete(f"/api/contacts/{self.a_ann.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_ann.refresh_from_db()
        self.assertTrue(self.a_ann.is_deleted)
        self.assertIsNone(self.a_ann.account_id)

    def test_delete_of_foreign_contact_is_404_and_changes_nothing(self):
        task = make_task(self.admin_b, self.b_bob, "B task", date(2026, 12, 1), "Not Started")
        before = DjangoContactModel.objects.get(id=self.b_bob.id)

        foreign = self.client_a.delete(f"/api/contacts/{self.b_bob.id}/delete/")
        missing = self.client_a.delete(f"/api/contacts/{uuid.uuid4()}/delete/")

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.data, {"detail": "Contact not found."})
        self.assert_same_as_missing(foreign, missing)

        after = DjangoContactModel.objects.get(id=self.b_bob.id)
        self.assertFalse(after.is_deleted)
        self.assertEqual(after.account_id, self.account_b.id)
        self.assertEqual(after.updated_at, before.updated_at)
        # No cleanup ran: the foreign contact's task is untouched.
        task.refresh_from_db()
        self.assertFalse(task.is_deleted)


class ContactCreateIsolationTests(TwoCompaniesContactsTestCase):

    def create(self, client, **payload):
        payload.setdefault("name", "New Contact")
        return client.post("/api/contacts/create/", payload, format="json")

    def test_create_stamps_the_actors_company(self):
        response = self.create(self.client_a, name="Created By A")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.company_id, self.company_a.id)
        self.assertEqual(contact.contact_owner_id, self.superadmin_a.id)

        response = self.create(self.client_b, name="Created By B")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.company_id, self.company_b.id)

    def test_create_with_own_account_and_owner_is_allowed(self):
        response = self.create(
            self.client_a,
            account_id=str(self.account_a.id),
            contact_owner_id=str(self.admin_a.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.account_id, self.account_a.id)
        self.assertEqual(contact.contact_owner_id, self.admin_a.id)

    def test_company_in_the_body_is_ignored(self):
        response = self.create(
            self.client_a,
            name="Sneaky",
            company=str(self.company_b.id),
            company_id=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.company_id, self.company_a.id)

    def test_company_in_query_string_and_headers_is_ignored(self):
        response = self.client_a.post(
            f"/api/contacts/create/?company_id={self.company_b.id}",
            {"name": "Sneaky 2"},
            format="json",
            HTTP_X_COMPANY_ID=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.company_id, self.company_a.id)

        listing = self.client_a.get(
            f"/api/contacts/?company_id={self.company_b.id}",
            HTTP_X_COMPANY_ID=str(self.company_b.id),
        )
        self.assertFalse(self.ids(listing) & self.all_b_ids)

    def test_create_with_foreign_account_is_rejected_like_an_unknown_account(self):
        total = DjangoContactModel.objects.count()

        foreign = self.create(self.client_a, account_id=str(self.account_b.id))
        missing = self.create(self.client_a, account_id=str(uuid.uuid4()))

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Account not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertEqual(DjangoContactModel.objects.count(), total)

    def test_create_with_foreign_owner_is_rejected_like_an_unknown_owner(self):
        total = DjangoContactModel.objects.count()

        foreign = self.create(self.client_a, contact_owner_id=str(self.admin_b.id))
        missing = self.create(self.client_a, contact_owner_id=str(uuid.uuid4()))

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Selected contact owner does not exist."})
        self.assert_same_as_missing(foreign, missing)
        self.assertEqual(DjangoContactModel.objects.count(), total)

    def test_create_reporting_to_a_foreign_contact_is_rejected(self):
        total = DjangoContactModel.objects.count()

        foreign = self.create(self.client_a, reporting_to_id=str(self.b_bob.id))
        missing = self.create(self.client_a, reporting_to_id=str(uuid.uuid4()))

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Reporting contact not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertEqual(DjangoContactModel.objects.count(), total)

    def test_create_reporting_to_an_own_contact_is_allowed(self):
        response = self.create(self.client_a, reporting_to_id=str(self.a_carl.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = DjangoContactModel.objects.get(id=response.data["id"])
        self.assertEqual(contact.reporting_to_id, self.a_carl.id)

    def test_same_contact_data_is_allowed_in_both_companies(self):
        response_a = self.create(self.client_a, name="Twin", email="twin@example.com")
        response_b = self.create(self.client_b, name="Twin", email="twin@example.com")

        self.assertEqual(response_a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_b.status_code, status.HTTP_201_CREATED)

        listing = self.client_a.get("/api/contacts/", {"search": "Twin"})
        self.assertEqual(self.ids(listing), {response_a.data["id"]})


class ContactRepositoryIsolationTests(TestCase):

    def setUp(self):
        self.company_a = make_company("Company A", "company-a")
        self.company_b = make_company("Company B", "company-b")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "admin-a@example.com")
        self.other_a = make_user(self.company_a, User.Role.ADMIN, "other-a@example.com")
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "admin-b@example.com")

        self.account_a = make_account(self.company_a, self.admin_a, "Acme A")
        self.account_b = make_account(self.company_b, self.admin_b, "Acme B")

        self.a_one = make_contact(
            self.company_a, self.admin_a, "Same Person", account=self.account_a,
            email="same@example.com", phone="5550001", mobile="5559999",
        )
        self.a_two = make_contact(self.company_a, self.admin_a, "A Two")
        self.a_deleted = make_contact(
            self.company_a, self.admin_a, "A Deleted", is_deleted=True,
        )
        self.b_one = make_contact(
            self.company_b, self.admin_b, "Same Person", account=self.account_b,
            email="same@example.com", phone="5550001", mobile="5559999",
        )
        self.b_two = make_contact(
            self.company_b, self.admin_b, "B Two", account=self.account_b,
        )

        self.repo_a = DjangoContactRepository(company_id=self.company_a.id)
        self.repo_b = DjangoContactRepository(company_id=self.company_b.id)

    def new_contact(self, **overrides):
        values = dict(
            account_id=None,
            contact_owner_id=self.admin_a.id,
            name="Brand New",
            email=None, secondary_email=None, phone=None, other_phone=None,
            mobile=None, home_phone=None, assistant_phone=None, title=None,
            department=None, lead_source=None, vendor_name=None,
            date_of_birth=None, assistant=None, email_opt_out=False,
            reporting_to_id=None, mailing_address=None, mailing_city=None,
            mailing_state=None, mailing_country=None, mailing_postal_code=None,
            other_address=None, description=None,
            created_by_id=self.admin_a.id,
        )
        values.update(overrides)
        return Contact.create(**values)

    def test_company_id_is_required(self):
        with self.assertRaises(ValueError) as raised:
            DjangoContactRepository(company_id=None)
        self.assertEqual(str(raised.exception), "company_id is required.")

        with self.assertRaises(TypeError):
            DjangoContactRepository()

    def test_get_by_id_only_sees_own_company(self):
        self.assertEqual(self.repo_a.get_by_id(self.a_one.id).id, self.a_one.id)
        self.assertIsNone(self.repo_a.get_by_id(self.b_one.id))
        self.assertIsNone(self.repo_b.get_by_id(self.a_one.id))

    def test_get_by_id_with_relations_only_sees_own_company(self):
        contact, account_name, owner_name = self.repo_a.get_by_id_with_relations(
            self.a_one.id,
        )

        self.assertEqual(contact.id, self.a_one.id)
        self.assertEqual(account_name, "Acme A")
        self.assertEqual(owner_name, self.admin_a.name)
        self.assertIsNone(self.repo_a.get_by_id_with_relations(self.b_one.id))

    def test_get_all_with_relations_only_sees_own_company(self):
        result = self.repo_a.get_all_with_relations(ListQuery(page_size=50))

        self.assertEqual(result.total, 2)
        self.assertEqual(
            {row[0].id for row in result.results}, {self.a_one.id, self.a_two.id},
        )

        searched = self.repo_a.get_all_with_relations(ListQuery(search="Same"))
        self.assertEqual([row[0].id for row in searched.results], [self.a_one.id])

        filtered = self.repo_a.get_all_with_relations(ListQuery(filters=(
            FilterCondition("account", "equals", str(self.account_b.id)),
        )))
        self.assertEqual(filtered.total, 0)

        ordered = self.repo_a.get_all_with_relations(
            ListQuery(sort_by="name", sort_direction="asc"),
        )
        self.assertEqual(
            [row[0].name for row in ordered.results], ["A Two", "Same Person"],
        )

    def test_get_all_with_relations_keeps_next_task_columns(self):
        make_task(self.admin_a, self.a_one, "Next", date(2026, 12, 31), "In Progress")

        result = self.repo_a.get_all_with_relations(ListQuery(search="Same"))

        _, _, _, next_due, next_status = result.results[0]
        self.assertEqual(next_due, date(2026, 12, 31))
        self.assertEqual(next_status, "In Progress")

    def test_get_by_account_id_with_owner_only_sees_own_company(self):
        self.assertEqual(
            [contact.id for contact, _ in self.repo_a.get_by_account_id_with_owner(
                self.account_a.id,
            )],
            [self.a_one.id],
        )
        self.assertEqual(self.repo_a.get_by_account_id_with_owner(self.account_b.id), [])

        # A stray row of company B pointing at company A's account is hidden.
        make_contact(self.company_b, self.admin_b, "Stray", account=self.account_a)
        self.assertEqual(
            [contact.id for contact, _ in self.repo_a.get_by_account_id_with_owner(
                self.account_a.id,
            )],
            [self.a_one.id],
        )

    def test_find_conversion_matches_only_sees_own_company(self):
        matches = self.repo_a.find_conversion_matches(
            name="same person", email="same@example.com",
            phone="5550001", mobile="5559999",
        )
        self.assertEqual([contact.id for contact in matches], [self.a_one.id])

        matches = self.repo_b.find_conversion_matches(
            name="same person", email=None, phone=None, mobile=None,
        )
        self.assertEqual([contact.id for contact in matches], [self.b_one.id])

        make_contact(
            self.company_b, self.admin_b, "Only In B",
            email="onlyb@example.com", phone="777", mobile="888",
        )
        self.assertEqual(
            self.repo_a.find_conversion_matches(
                "only in b", "onlyb@example.com", "777", "888",
            ),
            [],
        )

    def test_unlink_account_contacts_never_touches_other_company(self):
        self.repo_a.unlink_account_contacts(self.account_b.id)

        self.b_one.refresh_from_db()
        self.b_two.refresh_from_db()
        self.assertEqual(self.b_one.account_id, self.account_b.id)
        self.assertEqual(self.b_two.account_id, self.account_b.id)

        self.repo_a.unlink_account_contacts(self.account_a.id)

        self.a_one.refresh_from_db()
        self.assertIsNone(self.a_one.account_id)

    def test_count_by_owner_id_only_counts_own_company(self):
        self.assertEqual(self.repo_a.count_by_owner_id(self.admin_a.id), 3)
        self.assertEqual(self.repo_a.count_by_owner_id(self.admin_b.id), 0)
        self.assertEqual(self.repo_b.count_by_owner_id(self.admin_b.id), 2)
        self.assertEqual(self.repo_b.count_by_owner_id(self.admin_a.id), 0)

    def test_transfer_ownership_never_touches_other_company(self):
        moved = self.repo_a.transfer_ownership(self.admin_b.id, self.other_a.id)

        self.assertEqual(moved, 0)
        self.assertEqual(
            DjangoContactModel.objects.filter(contact_owner=self.admin_b).count(), 2,
        )

        moved = self.repo_a.transfer_ownership(self.admin_a.id, self.other_a.id)

        self.assertEqual(moved, 3)
        self.assertEqual(
            DjangoContactModel.objects.filter(
                company=self.company_a, contact_owner=self.other_a,
            ).count(),
            3,
        )
        self.assertEqual(
            DjangoContactModel.objects.filter(contact_owner=self.admin_b).count(), 2,
        )

    def test_save_stamps_the_repository_company(self):
        saved = self.repo_a.save(self.new_contact())

        self.assertEqual(
            DjangoContactModel.objects.get(id=saved.id).company_id, self.company_a.id,
        )
        self.assertIsNotNone(self.repo_a.get_by_id(saved.id))
        self.assertIsNone(self.repo_b.get_by_id(saved.id))

    def test_save_with_an_id_of_another_company_fails_closed(self):
        entity = self.repo_b.get_by_id(self.b_one.id)
        entity.name = "Hijacked"

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.repo_a.save(entity)

        row = DjangoContactModel.objects.get(id=self.b_one.id)
        self.assertEqual(row.name, "Same Person")
        self.assertEqual(row.company_id, self.company_b.id)
        self.assertEqual(DjangoContactModel.objects.filter(id=self.b_one.id).count(), 1)

    def test_save_rejects_reporting_to_a_contact_of_another_company(self):
        total = DjangoContactModel.objects.count()

        with self.assertRaises(ValueError) as raised:
            self.repo_a.save(self.new_contact(reporting_to_id=self.b_one.id))

        self.assertEqual(str(raised.exception), "Reporting contact not found.")
        self.assertEqual(DjangoContactModel.objects.count(), total)

        saved = self.repo_a.save(self.new_contact(reporting_to_id=self.a_two.id))
        self.assertEqual(saved.reporting_to_id, self.a_two.id)
