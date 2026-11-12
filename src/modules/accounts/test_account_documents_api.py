from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_document_model import (
    DjangoAccountDocumentModel,
)
from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.timeline.infrastructure.persistence.models import TimelineEvent
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


class AccountDocumentsTestCase(APITestCase):

    def setUp(self):
        self.company_a = make_company("Company A", "docs-company-a")
        self.company_b = make_company("Company B", "docs-company-b")

        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "docs-a@example.com")
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "docs-b@example.com")

        self.client_a = authenticated_client(self.admin_a)
        self.client_b = authenticated_client(self.admin_b)

        self.account_a = make_account(self.company_a, self.admin_a, "Alpha Co")
        self.account_b = make_account(self.company_b, self.admin_b, "Beta Co")

    def docs_url(self, account, document=None):
        base = f"/api/accounts/{account.id}/documents/"
        return base if document is None else f"{base}{document}/"

    def add(self, client, account, name="Contract", url="https://example.com/c.pdf"):
        return client.post(
            self.docs_url(account),
            {"name": name, "url": url},
            format="json",
        )


class AddAccountDocumentTests(AccountDocumentsTestCase):

    def test_add_document(self):
        response = self.add(self.client_a, self.account_a)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Contract")
        self.assertEqual(response.data["url"], "https://example.com/c.pdf")
        self.assertEqual(response.data["created_by_id"], self.admin_a.id)

        stored = DjangoAccountDocumentModel.objects.get(id=response.data["id"])
        self.assertEqual(stored.company_id, self.company_a.id)
        self.assertEqual(stored.account_id, self.account_a.id)

    def test_many_documents_can_be_added_to_one_account(self):
        for index in range(5):
            response = self.add(
                self.client_a, self.account_a,
                name=f"Doc {index}", url=f"https://example.com/{index}",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        listing = self.client_a.get(self.docs_url(self.account_a))
        self.assertEqual(
            [row["name"] for row in listing.data],
            [f"Doc {index}" for index in range(5)],
        )

    def test_name_and_url_are_required(self):
        for body in ({}, {"name": "Only name"}, {"url": "https://example.com"}):
            response = self.client_a.post(
                self.docs_url(self.account_a), body, format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_name_is_rejected(self):
        response = self.add(self.client_a, self.account_a, name="   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_http_and_https_links_are_accepted(self):
        for bad in (
            "javascript:alert(1)",
            "ftp://example.com/file",
            "example.com/file",
            "https://",
            "https://exa mple.com",
        ):
            response = self.add(self.client_a, self.account_a, url=bad)
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, msg=bad,
            )

        self.assertEqual(DjangoAccountDocumentModel.objects.count(), 0)

    def test_name_and_url_are_trimmed(self):
        response = self.add(
            self.client_a, self.account_a,
            name="  Signed   contract ", url="  https://example.com/x  ",
        )
        self.assertEqual(response.data["name"], "Signed contract")
        self.assertEqual(response.data["url"], "https://example.com/x")

    def test_add_records_timeline_event(self):
        self.add(self.client_a, self.account_a)
        self.assertTrue(
            TimelineEvent.objects.filter(
                event_type="ACCOUNT_DOCUMENT_ADDED",
            ).exists()
        )

    def test_deleted_account_is_not_found(self):
        self.account_a.is_deleted = True
        self.account_a.save()

        response = self.add(self.client_a, self.account_a)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_authentication_is_required(self):
        response = self.client.post(
            self.docs_url(self.account_a),
            {"name": "x", "url": "https://example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ListUpdateDeleteAccountDocumentTests(AccountDocumentsTestCase):

    def test_update_document(self):
        document_id = self.add(self.client_a, self.account_a).data["id"]

        response = self.client_a.put(
            self.docs_url(self.account_a, document_id),
            {"name": "Renamed", "url": "https://example.com/new"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Renamed")
        self.assertEqual(response.data["url"], "https://example.com/new")

        stored = DjangoAccountDocumentModel.objects.get(id=document_id)
        self.assertEqual(stored.name, "Renamed")
        self.assertEqual(stored.modified_by_id, self.admin_a.id)

    def test_update_with_invalid_url_is_rejected(self):
        document_id = self.add(self.client_a, self.account_a).data["id"]

        response = self.client_a.put(
            self.docs_url(self.account_a, document_id),
            {"name": "Renamed", "url": "not-a-url"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            DjangoAccountDocumentModel.objects.get(id=document_id).name, "Contract",
        )

    def test_delete_document(self):
        document_id = self.add(self.client_a, self.account_a).data["id"]

        response = self.client_a.delete(self.docs_url(self.account_a, document_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            DjangoAccountDocumentModel.objects.filter(id=document_id).exists()
        )
        self.assertTrue(
            TimelineEvent.objects.filter(
                event_type="ACCOUNT_DOCUMENT_DELETED",
            ).exists()
        )

    def test_unknown_document_is_not_found(self):
        missing = "00000000-0000-0000-0000-000000000001"

        for response in (
            self.client_a.put(
                self.docs_url(self.account_a, missing),
                {"name": "x", "url": "https://example.com"},
                format="json",
            ),
            self.client_a.delete(self.docs_url(self.account_a, missing)),
        ):
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_account_details_include_documents(self):
        self.add(self.client_a, self.account_a, name="Doc 1")
        self.add(self.client_a, self.account_a, name="Doc 2")

        response = self.client_a.get(f"/api/accounts/{self.account_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["name"] for row in response.data["documents"]],
            ["Doc 1", "Doc 2"],
        )

    def test_account_details_without_documents_return_empty_list(self):
        response = self.client_a.get(f"/api/accounts/{self.account_a.id}/")
        self.assertEqual(response.data["documents"], [])


class AccountDocumentTenantIsolationTests(AccountDocumentsTestCase):

    def test_other_company_cannot_list_add_update_or_delete(self):
        document_id = self.add(self.client_a, self.account_a).data["id"]

        url = self.docs_url(self.account_a)
        detail = self.docs_url(self.account_a, document_id)
        body = {"name": "Hacked", "url": "https://evil.example.com"}

        responses = (
            self.client_b.get(url),
            self.client_b.post(url, body, format="json"),
            self.client_b.put(detail, body, format="json"),
            self.client_b.delete(detail),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        stored = DjangoAccountDocumentModel.objects.get(id=document_id)
        self.assertEqual(stored.name, "Contract")

    def test_foreign_account_looks_the_same_as_a_missing_one(self):
        foreign = self.client_b.get(self.docs_url(self.account_a))

        class Missing:
            id = "00000000-0000-0000-0000-000000000002"

        missing = self.client_b.get(self.docs_url(Missing))

        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)

    def test_document_of_another_account_cannot_be_reached_through_this_one(self):
        other_account = make_account(self.company_a, self.admin_a, "Second Co")
        document_id = self.add(self.client_a, other_account).data["id"]

        response = self.client_a.delete(self.docs_url(self.account_a, document_id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            DjangoAccountDocumentModel.objects.filter(id=document_id).exists()
        )


class CreateAccountWithDocumentsTests(AccountDocumentsTestCase):

    def create(self, client, **extra):
        return client.post(
            "/api/accounts/create/",
            {"account_name": "Gamma Co", **extra},
            format="json",
        )

    def test_account_is_created_with_its_documents(self):
        response = self.create(
            self.client_a,
            documents=[
                {"name": "Contract", "url": "https://example.com/c.pdf"},
                {"name": "NDA", "url": "https://example.com/nda.pdf"},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        stored = DjangoAccountDocumentModel.objects.filter(
            account_id=response.data["id"],
        ).order_by("created_at")
        self.assertEqual([doc.name for doc in stored], ["Contract", "NDA"])
        self.assertTrue(all(doc.company_id == self.company_a.id for doc in stored))
        self.assertEqual(
            TimelineEvent.objects.filter(event_type="ACCOUNT_DOCUMENT_ADDED").count(),
            2,
        )

    def test_documents_are_optional(self):
        response = self.create(self.client_a)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DjangoAccountDocumentModel.objects.count(), 0)

    def test_invalid_document_url_creates_nothing(self):
        response = self.create(
            self.client_a,
            documents=[
                {"name": "Good", "url": "https://example.com/ok"},
                {"name": "Bad", "url": "javascript:alert(1)"},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            DjangoAccountModel.objects.filter(account_name="Gamma Co").exists()
        )
        self.assertEqual(DjangoAccountDocumentModel.objects.count(), 0)

    def test_created_documents_show_in_account_details(self):
        account_id = self.create(
            self.client_a,
            documents=[{"name": "Contract", "url": "https://example.com/c.pdf"}],
        ).data["id"]

        response = self.client_a.get(f"/api/accounts/{account_id}/")

        self.assertEqual(
            [row["name"] for row in response.data["documents"]], ["Contract"],
        )


class AccountOwnerTests(AccountDocumentsTestCase):
    """The owner chosen in the create / edit form must actually be saved."""

    def setUp(self):
        super().setUp()
        self.colleague_a = make_user(
            self.company_a, User.Role.ADMIN, "colleague-a@example.com",
        )

    def test_create_uses_the_chosen_owner(self):
        response = self.client_a.post(
            "/api/accounts/create/",
            {"account_name": "Gamma Co", "account_owner_id": str(self.colleague_a.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            DjangoAccountModel.objects.get(id=response.data["id"]).account_owner_id,
            self.colleague_a.id,
        )

    def test_create_without_owner_defaults_to_the_creator(self):
        response = self.client_a.post(
            "/api/accounts/create/", {"account_name": "Gamma Co"}, format="json",
        )

        self.assertEqual(
            DjangoAccountModel.objects.get(id=response.data["id"]).account_owner_id,
            self.admin_a.id,
        )

    def update(self, client, account, **extra):
        return client.put(
            f"/api/accounts/{account.id}/update",
            {"account_name": account.account_name, **extra},
            format="json",
        )

    def test_update_changes_the_owner(self):
        response = self.update(
            self.client_a, self.account_a,
            account_owner_id=str(self.colleague_a.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.account_a.refresh_from_db()
        self.assertEqual(self.account_a.account_owner_id, self.colleague_a.id)
        event = TimelineEvent.objects.get(event_type="ACCOUNT_UPDATED")
        self.assertIn(self.colleague_a.name, event.message)
        self.assertNotIn(str(self.colleague_a.id), event.message)

    def test_update_without_owner_keeps_the_owner(self):
        response = self.update(self.client_a, self.account_a, phone="123")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.account_a.refresh_from_db()
        self.assertEqual(self.account_a.account_owner_id, self.admin_a.id)

    def test_owner_from_another_company_is_rejected(self):
        response = self.update(
            self.client_a, self.account_a, account_owner_id=str(self.admin_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.account_a.refresh_from_db()
        self.assertEqual(self.account_a.account_owner_id, self.admin_a.id)
