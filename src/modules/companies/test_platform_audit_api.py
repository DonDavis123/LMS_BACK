import json

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from src.modules.companies.infrastructure.persistence.platform_audit_log_model import (
    PlatformAuditLogModel,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

BASE = "/api/platform/companies/"
AUDIT = "/api/platform/audit-logs/"
Action = PlatformAuditLogModel.Action


class PlatformAuditApiTests(APITestCase):

    def setUp(self):
        self.platform_admin = make_user(
            None, role=User.Role.PLATFORM_SUPERADMIN, email="platform@example.com"
        )
        self.client = authenticated_client(self.platform_admin)

    def entries(self, action=None, company_id=None):
        queryset = PlatformAuditLogModel.objects.all()
        if action:
            queryset = queryset.filter(action=action)
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset

    def create_company(self):
        response = self.client.post(
            BASE,
            {
                "company_name": "Acme Corp",
                "admin_name": "Alice",
                "admin_email": "alice@acme.example.com",
                "admin_password": "s3cret-pass",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def assert_one_entry(self, action, company_id):
        entries = self.entries(action, company_id)
        self.assertEqual(entries.count(), 1, action)
        entry = entries.get()
        self.assertEqual(entry.actor_id, self.platform_admin.id)
        self.assertEqual(entry.actor_email, "platform@example.com")
        return entry

    def test_every_write_action_creates_exactly_one_entry(self):
        data = self.create_company()
        company_id = data["company"]["id"]
        admin_id = data["admin"]["id"]

        created = self.assert_one_entry(Action.COMPANY_CREATED, company_id)
        self.assertEqual(str(created.target_user_id), admin_id)
        self.assertEqual(created.target_email, "alice@acme.example.com")

        self.client.patch(f"{BASE}{company_id}/", {"name": "Acme 2"}, format="json")
        updated = self.assert_one_entry(Action.COMPANY_UPDATED, company_id)
        self.assertEqual(updated.metadata, {"changed_fields": ["name"]})

        self.client.post(
            f"{BASE}{company_id}/suspend/", {"reason": "Unpaid"}, format="json"
        )
        suspended = self.assert_one_entry(Action.COMPANY_SUSPENDED, company_id)
        self.assertEqual(suspended.metadata, {"reason": "Unpaid"})

        self.client.post(f"{BASE}{company_id}/activate/")
        self.assert_one_entry(Action.COMPANY_ACTIVATED, company_id)

        users = f"{BASE}{company_id}/users/"
        created_user = self.client.post(
            users,
            {
                "name": "Bob",
                "email": "bob@acme.example.com",
                "password": "bobs-password",
                "role": "ADMIN",
            },
            format="json",
        )
        bob_id = created_user.data["id"]
        entry = self.assert_one_entry(Action.COMPANY_USER_CREATED, company_id)
        self.assertEqual(str(entry.target_user_id), bob_id)
        self.assertEqual(entry.metadata, {"role": "ADMIN"})

        self.client.post(
            f"{users}{bob_id}/reset-password/",
            {"new_password": "new-secret-pass"},
            format="json",
        )
        self.assert_one_entry(Action.COMPANY_USER_PASSWORD_RESET, company_id)

        self.client.post(f"{users}{bob_id}/block/")
        self.assert_one_entry(Action.COMPANY_USER_BLOCKED, company_id)

        self.client.post(f"{users}{bob_id}/unblock/")
        self.assert_one_entry(Action.COMPANY_USER_UNBLOCKED, company_id)

        self.assertEqual(PlatformAuditLogModel.objects.count(), 8)

    def test_no_secrets_in_audit_entries(self):
        data = self.create_company()
        company_id = data["company"]["id"]
        bob = self.client.post(
            f"{BASE}{company_id}/users/",
            {
                "name": "Bob",
                "email": "bob@acme.example.com",
                "password": "bobs-password",
                "role": "ADMIN",
            },
            format="json",
        ).data
        self.client.post(
            f"{BASE}{company_id}/users/{bob['id']}/reset-password/",
            {"new_password": "new-secret-pass"},
            format="json",
        )

        dumped = json.dumps(
            list(PlatformAuditLogModel.objects.values("metadata", "target_email"))
        ) + json.dumps(self.client.get(AUDIT).data, default=str)

        for secret in ("s3cret-pass", "bobs-password", "new-secret-pass", "password"):
            self.assertNotIn(secret, dumped)

    def test_failed_actions_leave_no_entries(self):
        company = make_company("Acme")
        make_user(company, email="taken@example.com")

        self.client.post(
            BASE,
            {
                "company_name": "Dup",
                "admin_name": "D",
                "admin_email": "taken@example.com",
                "admin_password": "s3cret-pass",
            },
            format="json",
        )
        self.client.post(f"{BASE}{company.id}/suspend/", {"reason": ""}, format="json")

        self.assertEqual(PlatformAuditLogModel.objects.count(), 0)

    def test_list_filters_pagination_and_order(self):
        first = self.create_company()["company"]["id"]
        other = make_company("Other")
        self.client.post(f"{BASE}{other.id}/suspend/", {"reason": "x"}, format="json")
        self.client.post(f"{BASE}{other.id}/activate/")

        everything = self.client.get(AUDIT)
        self.assertEqual(everything.status_code, status.HTTP_200_OK)
        self.assertEqual(everything.data["pagination"]["total"], 3)
        self.assertEqual(everything.data["results"][0]["action"], "COMPANY_ACTIVATED")
        self.assertEqual(
            set(everything.data["results"][0]),
            {
                "id", "action", "actor_id", "actor_email", "company_id",
                "target_user_id", "target_email", "metadata", "created_at",
            },
        )

        by_company = self.client.get(AUDIT, {"company_id": first})
        self.assertEqual(
            [e["action"] for e in by_company.data["results"]], ["COMPANY_CREATED"]
        )

        by_action = self.client.get(AUDIT, {"action": "COMPANY_SUSPENDED"})
        self.assertEqual(len(by_action.data["results"]), 1)
        self.assertEqual(by_action.data["results"][0]["company_id"], str(other.id))

        paged = self.client.get(AUDIT, {"page_size": 2, "page": 2})
        self.assertEqual(len(paged.data["results"]), 1)
        self.assertEqual(paged.data["pagination"]["total_pages"], 2)

    def test_list_rejects_bad_filters(self):
        for params in ({"company_id": "nope"}, {"action": "NOPE"}, {"page": "0"}):
            with self.subTest(params=params):
                response = self.client.get(AUDIT, params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_platform_users_are_forbidden(self):
        company = make_company("Tenant")
        for role in (User.Role.SUPERADMIN, User.Role.ADMIN):
            with self.subTest(role=role):
                client = authenticated_client(make_user(company, role=role))
                self.assertEqual(
                    client.get(AUDIT).status_code, status.HTTP_403_FORBIDDEN
                )
        self.assertIn(
            APIClient().get(AUDIT).status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )
