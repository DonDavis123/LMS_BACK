import json
import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
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


class TwoCompaniesAccountsTestCase(APITestCase):
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

        # Both companies deliberately own an account with the same name.
        self.a_alpha = make_account(
            self.company_a, self.admin_a, "Alpha Co",
            website="https://same.example.com", phone="111111",
        )
        self.a_shared = make_account(
            self.company_a, self.superadmin_a, "Shared Name",
            website="https://same.example.com", phone="111111",
        )
        self.a_gamma = make_account(self.company_a, self.admin_a, "Gamma Co")

        self.b_beta = make_account(
            self.company_b, self.admin_b, "Beta Co",
            website="https://same.example.com", phone="111111",
        )
        self.b_shared = make_account(
            self.company_b, self.superadmin_b, "Shared Name",
            website="https://same.example.com", phone="111111",
        )
        self.b_delta = make_account(self.company_b, self.admin_b, "Delta Co")

    @staticmethod
    def filters(*conditions):
        return json.dumps(list(conditions))

    @staticmethod
    def ids(response):
        return {row["id"] for row in response.data["results"]}

    @staticmethod
    def names(response):
        return [row["account_name"] for row in response.data["results"]]

    def assert_same_as_missing(self, foreign_response, missing_response):
        """A foreign record must be indistinguishable from a missing one."""
        self.assertEqual(foreign_response.status_code, missing_response.status_code)
        self.assertEqual(foreign_response.data, missing_response.data)


class AccountListIsolationTests(TwoCompaniesAccountsTestCase):

    def test_list_returns_only_own_accounts(self):
        response = self.client_a.get("/api/accounts/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.ids(response),
            {str(self.a_alpha.id), str(self.a_shared.id), str(self.a_gamma.id)},
        )
        self.assertEqual(response.data["pagination"]["total"], 3)

        response = self.client_b.get("/api/accounts/", {"page_size": 50})

        self.assertEqual(
            self.ids(response),
            {str(self.b_beta.id), str(self.b_shared.id), str(self.b_delta.id)},
        )
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_list_works_with_real_jwt_authentication(self):
        response = token_client(self.superadmin_a).get("/api/accounts/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_search_never_includes_other_company_accounts(self):
        response = self.client_a.get("/api/accounts/", {"search": "Shared"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {str(self.a_shared.id)})
        self.assertEqual(response.data["pagination"]["total"], 1)

        for term in ("Beta", "Delta", "same.example.com"):
            with self.subTest(term=term):
                response = self.client_a.get("/api/accounts/", {"search": term})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertFalse(
                    self.ids(response)
                    & {str(self.b_beta.id), str(self.b_shared.id), str(self.b_delta.id)}
                )

        response = self.client_a.get("/api/accounts/", {"search": "Beta"})
        self.assertEqual(response.data["pagination"]["total"], 0)

    def test_filters_never_include_other_company_accounts(self):
        response = self.client_a.get("/api/accounts/", {
            "filters": self.filters(
                {"field": "account_name", "operator": "equals", "value": "Shared Name"},
            ),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {str(self.a_shared.id)})

        response = self.client_a.get("/api/accounts/", {
            "filters": self.filters(
                {"field": "account_name", "operator": "not_equals", "value": "Shared Name"},
            ),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.ids(response), {str(self.a_alpha.id), str(self.a_gamma.id)},
        )

        response = self.client_a.get("/api/accounts/", {
            "filters": self.filters(
                {"field": "account_owner", "operator": "equals", "value": str(self.admin_b.id)},
            ),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["pagination"]["total"], 0)

    def test_sorting_never_includes_other_company_accounts(self):
        response = self.client_a.get("/api/accounts/", {
            "sort_by": "account_name", "sort_direction": "asc", "page_size": 50,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names(response), ["Alpha Co", "Gamma Co", "Shared Name"])

        response = self.client_a.get("/api/accounts/", {
            "sort_by": "account_name", "sort_direction": "desc", "page_size": 50,
        })
        self.assertEqual(self.names(response), ["Shared Name", "Gamma Co", "Alpha Co"])

        response = self.client_a.get("/api/accounts/", {
            "sort_by": "account_owner", "sort_direction": "asc", "page_size": 50,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 3)

    def test_pagination_never_includes_other_company_accounts(self):
        seen = set()
        for page in (1, 2):
            response = self.client_a.get("/api/accounts/", {"page": page, "page_size": 2})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["pagination"]["total"], 3)
            self.assertEqual(response.data["pagination"]["total_pages"], 2)
            seen |= self.ids(response)

        self.assertEqual(
            seen,
            {str(self.a_alpha.id), str(self.a_shared.id), str(self.a_gamma.id)},
        )

        response = self.client_a.get("/api/accounts/", {"page": 3, "page_size": 2})
        self.assertEqual(response.data["results"], [])

    def test_soft_deleted_accounts_stay_hidden_inside_the_company(self):
        self.a_gamma.is_deleted = True
        self.a_gamma.save(update_fields=["is_deleted"])

        response = self.client_a.get("/api/accounts/", {"page_size": 50})

        self.assertEqual(response.data["pagination"]["total"], 2)
        self.assertNotIn(str(self.a_gamma.id), self.ids(response))

    def test_platform_superadmin_cannot_reach_company_accounts(self):
        platform = make_user(None, User.Role.PLATFORM_SUPERADMIN, "platform@example.com")
        client = authenticated_client(platform)

        self.assertEqual(
            client.get("/api/accounts/").status_code, status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            client.post(
                "/api/accounts/create/", {"account_name": "Nope"}, format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            client.get(f"/api/accounts/{self.a_alpha.id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )


class AccountDetailIsolationTests(TwoCompaniesAccountsTestCase):

    def test_detail_of_own_account_is_returned(self):
        response = self.client_a.get(f"/api/accounts/{self.a_alpha.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.a_alpha.id))
        self.assertEqual(response.data["account_name"], "Alpha Co")

    def test_detail_of_foreign_account_is_404_like_a_missing_one(self):
        foreign = self.client_a.get(f"/api/accounts/{self.b_beta.id}/")
        missing = self.client_a.get(f"/api/accounts/{uuid.uuid4()}/")

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.data, {"detail": "Account not found."})
        self.assert_same_as_missing(foreign, missing)

    def test_detail_lists_only_own_contacts(self):
        own_contact = make_contact(
            self.company_a, self.admin_a, "Own Contact", account=self.a_alpha,
        )
        # Stray row of another company that points at company A's account
        # (e.g. legacy/corrupt data): it must never be shown.
        foreign_contact = make_contact(
            self.company_b, self.admin_b, "Foreign Contact", account=self.a_alpha,
        )

        response = self.client_a.get(f"/api/accounts/{self.a_alpha.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contact_ids = {row["id"] for row in response.data["contacts"]}
        self.assertEqual(contact_ids, {str(own_contact.id)})
        self.assertNotIn(str(foreign_contact.id), contact_ids)


class AccountUpdateIsolationTests(TwoCompaniesAccountsTestCase):

    def update(self, client, account_id, **payload):
        payload.setdefault("account_name", "Renamed")
        # The update use case writes every editable field; ownership is the
        # only non-nullable one, so a full payload always carries it.
        payload.setdefault("ownership", "None")
        return client.put(
            f"/api/accounts/{account_id}/update", payload, format="json",
        )

    def test_update_of_own_account_works(self):
        response = self.update(self.client_a, self.a_alpha.id, account_name="Alpha Renamed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_alpha.refresh_from_db()
        self.assertEqual(self.a_alpha.account_name, "Alpha Renamed")
        self.assertEqual(self.a_alpha.company_id, self.company_a.id)

    def test_update_of_foreign_account_is_rejected_and_changes_nothing(self):
        before = DjangoAccountModel.objects.get(id=self.b_beta.id)

        foreign = self.update(self.client_a, self.b_beta.id, account_name="Hijacked")
        missing = self.update(self.client_a, uuid.uuid4(), account_name="Hijacked")

        # Same response as for a record that does not exist.
        self.assertEqual(foreign.data, {"detail": "Account not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertIn(
            foreign.status_code,
            {status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND},
        )

        after = DjangoAccountModel.objects.get(id=self.b_beta.id)
        self.assertEqual(after.account_name, "Beta Co")
        self.assertEqual(after.company_id, self.company_b.id)
        self.assertEqual(after.updated_at, before.updated_at)
        self.assertEqual(after.modified_by_id, before.modified_by_id)

    def test_update_cannot_move_account_to_a_foreign_owner(self):
        # The update payload has no owner field: a foreign account_owner_id
        # (or company) in the body is ignored and never applied.
        response = self.update(
            self.client_a,
            self.a_alpha.id,
            account_name="Alpha Renamed",
            account_owner_id=str(self.admin_b.id),
            company=str(self.company_b.id),
            company_id=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_alpha.refresh_from_db()
        self.assertEqual(self.a_alpha.account_owner_id, self.admin_a.id)
        self.assertEqual(self.a_alpha.company_id, self.company_a.id)


class AccountDeleteIsolationTests(TwoCompaniesAccountsTestCase):

    def test_delete_of_own_account_works(self):
        response = self.client_a.delete(f"/api/accounts/{self.a_gamma.id}/delete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.a_gamma.refresh_from_db()
        self.assertTrue(self.a_gamma.is_deleted)

    def test_delete_of_foreign_account_is_404_and_changes_nothing(self):
        contact = make_contact(
            self.company_b, self.admin_b, "B Contact", account=self.b_beta,
        )
        before = DjangoAccountModel.objects.get(id=self.b_beta.id)

        foreign = self.client_a.delete(f"/api/accounts/{self.b_beta.id}/delete/")
        missing = self.client_a.delete(f"/api/accounts/{uuid.uuid4()}/delete/")

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.data, {"detail": "Account not found."})
        self.assert_same_as_missing(foreign, missing)

        after = DjangoAccountModel.objects.get(id=self.b_beta.id)
        self.assertFalse(after.is_deleted)
        self.assertEqual(after.updated_at, before.updated_at)
        # No cleanup ran: the foreign contact is still linked.
        contact.refresh_from_db()
        self.assertEqual(contact.account_id, self.b_beta.id)
        self.assertFalse(contact.is_deleted)


class AccountCreateIsolationTests(TwoCompaniesAccountsTestCase):

    def test_create_stamps_the_actors_company(self):
        response = self.client_a.post(
            "/api/accounts/create/", {"account_name": "Created By A"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        account = DjangoAccountModel.objects.get(id=response.data["id"])
        self.assertEqual(account.company_id, self.company_a.id)
        self.assertEqual(account.account_owner_id, self.superadmin_a.id)

        response = self.client_b.post(
            "/api/accounts/create/", {"account_name": "Created By B"}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        account = DjangoAccountModel.objects.get(id=response.data["id"])
        self.assertEqual(account.company_id, self.company_b.id)

    def test_company_in_the_body_is_ignored(self):
        response = self.client_a.post(
            "/api/accounts/create/",
            {
                "account_name": "Sneaky",
                "company": str(self.company_b.id),
                "company_id": str(self.company_b.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        account = DjangoAccountModel.objects.get(id=response.data["id"])
        self.assertEqual(account.company_id, self.company_a.id)

    def test_company_in_query_string_and_headers_is_ignored(self):
        response = self.client_a.post(
            f"/api/accounts/create/?company_id={self.company_b.id}",
            {"account_name": "Sneaky 2"},
            format="json",
            HTTP_X_COMPANY_ID=str(self.company_b.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        account = DjangoAccountModel.objects.get(id=response.data["id"])
        self.assertEqual(account.company_id, self.company_a.id)

        listing = self.client_a.get(
            f"/api/accounts/?company_id={self.company_b.id}",
            HTTP_X_COMPANY_ID=str(self.company_b.id),
        )
        self.assertNotIn(str(self.b_beta.id), self.ids(listing))

    def test_create_with_foreign_owner_is_rejected_like_an_unknown_owner(self):
        total = DjangoAccountModel.objects.count()

        foreign = self.client_a.post(
            "/api/accounts/create/",
            {"account_name": "Foreign Owner", "account_owner_id": str(self.admin_b.id)},
            format="json",
        )
        missing = self.client_a.post(
            "/api/accounts/create/",
            {"account_name": "Foreign Owner", "account_owner_id": str(uuid.uuid4())},
            format="json",
        )

        self.assertEqual(foreign.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.data, {"detail": "Account owner not found."})
        self.assert_same_as_missing(foreign, missing)
        self.assertEqual(DjangoAccountModel.objects.count(), total)

    def test_create_with_own_company_owner_is_allowed(self):
        response = self.client_a.post(
            "/api/accounts/create/",
            {"account_name": "Owned By Admin", "account_owner_id": str(self.admin_a.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        account = DjangoAccountModel.objects.get(id=response.data["id"])
        self.assertEqual(account.account_owner_id, self.admin_a.id)

    def test_same_account_name_is_allowed_in_both_companies(self):
        response_a = self.client_a.post(
            "/api/accounts/create/", {"account_name": "Twin"}, format="json",
        )
        response_b = self.client_b.post(
            "/api/accounts/create/", {"account_name": "Twin"}, format="json",
        )

        self.assertEqual(response_a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_b.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            DjangoAccountModel.objects.filter(
                account_name="Twin", company=self.company_a,
            ).count(),
            1,
        )
        self.assertEqual(
            DjangoAccountModel.objects.filter(
                account_name="Twin", company=self.company_b,
            ).count(),
            1,
        )

        listing = self.client_a.get("/api/accounts/", {"search": "Twin"})
        self.assertEqual(self.ids(listing), {response_a.data["id"]})


class AccountRepositoryIsolationTests(TestCase):

    def setUp(self):
        self.company_a = make_company("Company A", "company-a")
        self.company_b = make_company("Company B", "company-b")
        self.admin_a = make_user(self.company_a, User.Role.ADMIN, "admin-a@example.com")
        self.other_a = make_user(self.company_a, User.Role.ADMIN, "other-a@example.com")
        self.admin_b = make_user(self.company_b, User.Role.ADMIN, "admin-b@example.com")

        self.a_one = make_account(
            self.company_a, self.admin_a, "Shared Name",
            website="https://same.example.com", phone="111111",
        )
        self.a_two = make_account(self.company_a, self.admin_a, "A Two")
        self.a_deleted = make_account(
            self.company_a, self.admin_a, "A Deleted", is_deleted=True,
        )
        self.b_one = make_account(
            self.company_b, self.admin_b, "Shared Name",
            website="https://same.example.com", phone="111111",
        )
        self.b_two = make_account(self.company_b, self.admin_b, "B Two")

        self.repo_a = DjangoAccountRepository(company_id=self.company_a.id)
        self.repo_b = DjangoAccountRepository(company_id=self.company_b.id)

    def test_company_id_is_required(self):
        with self.assertRaises(ValueError) as raised:
            DjangoAccountRepository(company_id=None)
        self.assertEqual(str(raised.exception), "company_id is required.")

        with self.assertRaises(TypeError):
            DjangoAccountRepository()

    def test_get_by_id_only_sees_own_company(self):
        self.assertEqual(self.repo_a.get_by_id(self.a_one.id).id, self.a_one.id)
        self.assertIsNone(self.repo_a.get_by_id(self.b_one.id))
        self.assertIsNone(self.repo_b.get_by_id(self.a_one.id))

    def test_get_by_id_with_owner_only_sees_own_company(self):
        account, owner_name = self.repo_a.get_by_id_with_owner(self.a_one.id)

        self.assertEqual(account.id, self.a_one.id)
        self.assertEqual(owner_name, self.admin_a.name)
        self.assertIsNone(self.repo_a.get_by_id_with_owner(self.b_one.id))

    def test_get_all_only_sees_own_company(self):
        self.assertEqual(
            {account.id for account in self.repo_a.get_all()},
            {self.a_one.id, self.a_two.id},
        )
        self.assertEqual(
            {account.id for account in self.repo_b.get_all()},
            {self.b_one.id, self.b_two.id},
        )

    def test_get_all_with_owner_only_sees_own_company(self):
        result = self.repo_a.get_all_with_owner(ListQuery(page_size=50))

        self.assertEqual(result.total, 2)
        self.assertEqual(
            {account.id for account, _ in result.results},
            {self.a_one.id, self.a_two.id},
        )

        searched = self.repo_a.get_all_with_owner(ListQuery(search="Shared"))
        self.assertEqual([account.id for account, _ in searched.results], [self.a_one.id])

        filtered = self.repo_a.get_all_with_owner(ListQuery(filters=(
            FilterCondition("account_owner", "equals", str(self.admin_b.id)),
        )))
        self.assertEqual(filtered.total, 0)

        sorted_result = self.repo_a.get_all_with_owner(
            ListQuery(sort_by="account_name", sort_direction="asc"),
        )
        self.assertEqual(
            [account.account_name for account, _ in sorted_result.results],
            ["A Two", "Shared Name"],
        )

    def test_find_conversion_matches_only_sees_own_company(self):
        matches = self.repo_a.find_conversion_matches(
            account_name="shared name",
            website="https://same.example.com",
            phone="111111",
        )

        self.assertEqual([account.id for account in matches], [self.a_one.id])

        matches = self.repo_b.find_conversion_matches(
            account_name="shared name", website=None, phone=None,
        )
        self.assertEqual([account.id for account in matches], [self.b_one.id])

        # Only the other company has this name: no match at all.
        make_account(self.company_b, self.admin_b, "Only In B", phone="999999")
        self.assertEqual(
            self.repo_a.find_conversion_matches("only in b", None, "999999"), [],
        )

    def test_count_by_owner_id_only_counts_own_company(self):
        self.assertEqual(self.repo_a.count_by_owner_id(self.admin_a.id), 3)
        self.assertEqual(self.repo_a.count_by_owner_id(self.admin_b.id), 0)
        self.assertEqual(self.repo_b.count_by_owner_id(self.admin_b.id), 2)
        self.assertEqual(self.repo_b.count_by_owner_id(self.admin_a.id), 0)

    def test_transfer_ownership_never_touches_other_company(self):
        moved = self.repo_a.transfer_ownership(self.admin_b.id, self.other_a.id)

        self.assertEqual(moved, 0)
        self.assertEqual(
            DjangoAccountModel.objects.filter(account_owner=self.admin_b).count(), 2,
        )

        moved = self.repo_a.transfer_ownership(self.admin_a.id, self.other_a.id)

        self.assertEqual(moved, 3)
        self.assertEqual(
            DjangoAccountModel.objects.filter(
                company=self.company_a, account_owner=self.other_a,
            ).count(),
            3,
        )
        self.assertEqual(
            DjangoAccountModel.objects.filter(account_owner=self.admin_b).count(), 2,
        )

    def test_save_stamps_the_repository_company(self):
        from src.modules.accounts.domain.entities.account import Account

        account = Account.create(
            account_owner_id=self.admin_a.id,
            account_name="Brand New",
            account_site=None, account_number=None, account_type=None,
            industry=None, annual_revenue=None, rating=None, phone=None,
            website=None, ticker_symbol=None, ownership=None, employees=None,
            sic_code=None, billing_address=None, billing_city=None,
            billing_state=None, billing_country=None, billing_postal_code=None,
            description=None, created_by_id=self.admin_a.id,
        )

        saved = self.repo_a.save(account)

        self.assertEqual(
            DjangoAccountModel.objects.get(id=saved.id).company_id, self.company_a.id,
        )
        self.assertIsNotNone(self.repo_a.get_by_id(saved.id))
        self.assertIsNone(self.repo_b.get_by_id(saved.id))

    def test_save_with_an_id_of_another_company_fails_closed(self):
        entity = self.repo_b.get_by_id(self.b_one.id)
        entity.account_name = "Hijacked"

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.repo_a.save(entity)

        row = DjangoAccountModel.objects.get(id=self.b_one.id)
        self.assertEqual(row.account_name, "Shared Name")
        self.assertEqual(row.company_id, self.company_b.id)
        self.assertEqual(DjangoAccountModel.objects.filter(id=self.b_one.id).count(), 1)
