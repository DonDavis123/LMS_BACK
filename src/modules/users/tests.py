import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.users.infrastructure.persistence.models import User


class SuperadminUserManagementPresentationTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="superadmin@example.com",
            password="password123",
            name="Super Admin",
            role=User.Role.SUPERADMIN,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            name="Admin",
            role=User.Role.ADMIN,
        )
        self.sales_manager = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            name="Sales Manager",
            role=User.Role.SALES_MANAGER,
        )
        self.sales_executive = User.objects.create_user(
            email="executive@example.com",
            password="password123",
            name="Sales Executive",
            role=User.Role.SALES_EXECUTIVE,
        )
        self.target = User.objects.create_user(
            email="target@example.com",
            password="password123",
            name="Target User",
            role=User.Role.ADMIN,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_create_user_allows_superadmin(self):
        self.authenticate(self.superadmin)

        response = self.client.post(
            "/api/users/",
            {
                "name": "New User",
                "email": "new-user@example.com",
                "password": "newpassword123",
                "role": User.Role.SALES_EXECUTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "new-user@example.com")
        self.assertEqual(response.data["role"], User.Role.SALES_EXECUTIVE)
        self.assertNotIn("password", response.data)

    def test_create_user_rejects_invalid_request_data(self):
        self.authenticate(self.superadmin)

        response = self.client.post(
            "/api/users/",
            {
                "name": "",
                "email": "not-an-email",
                "password": "short",
                "role": User.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_rejects_duplicate_email(self):
        self.authenticate(self.superadmin)

        response = self.client.post(
            "/api/users/",
            {
                "name": "Duplicate",
                "email": self.admin.email,
                "password": "password123",
                "role": User.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_management_endpoints_reject_non_superadmins(self):
        for user in (
            self.admin,
            self.sales_manager,
            self.sales_executive,
        ):
            with self.subTest(role=user.role):
                self.authenticate(user)

                self.assertEqual(
                    self.client.get("/api/users/").status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.post(
                        "/api/users/",
                        {
                            "name": "Blocked",
                            "email": f"{uuid.uuid4()}@example.com",
                            "password": "password123",
                            "role": User.Role.ADMIN,
                        },
                        format="json",
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.get(
                        f"/api/users/{self.target.id}/"
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.patch(
                        f"/api/users/{self.target.id}/",
                        {"name": "Blocked"},
                        format="json",
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.post(
                        f"/api/users/{self.target.id}/block/"
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.post(
                        f"/api/users/{self.target.id}/unblock/"
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.delete(
                        f"/api/users/{self.target.id}/"
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )

    def test_user_management_endpoints_require_authentication(self):
        self.client.force_authenticate(None)

        self.assertEqual(
            self.client.get("/api/users/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.post(
                "/api/users/",
                {
                    "name": "Unauthenticated",
                    "email": "unauthenticated@example.com",
                    "password": "password123",
                    "role": User.Role.ADMIN,
                },
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(
                f"/api/users/{self.target.id}/"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/users/{self.target.id}/",
                {"name": "Unauthenticated"},
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.post(
                f"/api/users/{self.target.id}/block/"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.post(
                f"/api/users/{self.target.id}/unblock/"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/users/{self.target.id}/"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_list_users_supports_existing_pagination(self):
        self.authenticate(self.superadmin)

        response = self.client.get(
            "/api/users/?page=1&page_size=2"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page"], 1)
        self.assertEqual(response.data["pagination"]["page_size"], 2)
        self.assertEqual(response.data["pagination"]["total"], 5)
        self.assertEqual(response.data["pagination"]["total_pages"], 3)
        self.assertEqual(len(response.data["results"]), 2)

    def test_get_user_details(self):
        self.authenticate(self.superadmin)

        response = self.client.get(
            f"/api/users/{self.target.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.target.id))
        self.assertEqual(response.data["email"], self.target.email)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertNotIn("password", response.data)

    def test_get_user_details_returns_404_for_missing_user(self):
        self.authenticate(self.superadmin)

        response = self.client.get(
            f"/api/users/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_user_supports_partial_update(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/users/{self.target.id}/",
            {"name": "Updated Target"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Target")

        self.target.refresh_from_db()
        self.assertEqual(self.target.name, "Updated Target")

    def test_update_user_rejects_protected_or_unknown_fields(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/users/{self.target.id}/",
            {
                "name": "Should Not Update",
                "password": "changedpassword",
                "is_superuser": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.target.refresh_from_db()
        self.assertEqual(self.target.name, "Target User")
        self.assertFalse(self.target.is_superuser)

    def test_update_user_returns_404_for_missing_user(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/users/{uuid.uuid4()}/",
            {"name": "Missing"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_user_rejects_invalid_email(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/users/{self.target.id}/",
            {"email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_user_rejects_duplicate_email(self):
        self.authenticate(self.superadmin)

        response = self.client.patch(
            f"/api/users/{self.target.id}/",
            {"email": self.admin.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_block_and_unblock_user(self):
        self.authenticate(self.superadmin)

        block_response = self.client.post(
            f"/api/users/{self.target.id}/block/"
        )

        self.assertEqual(block_response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertFalse(block_response.data["is_active"])

        unblock_response = self.client.post(
            f"/api/users/{self.target.id}/unblock/"
        )

        self.assertEqual(unblock_response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(unblock_response.data["is_active"])

    def test_unblock_returns_404_for_missing_user(self):
        self.authenticate(self.superadmin)

        response = self.client.post(
            f"/api/users/{uuid.uuid4()}/unblock/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_block_returns_404_for_missing_user(self):
        self.authenticate(self.superadmin)

        response = self.client.post(
            f"/api/users/{uuid.uuid4()}/block/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_superadmin_cannot_block_or_delete_self(self):
        self.authenticate(self.superadmin)

        block_response = self.client.post(
            f"/api/users/{self.superadmin.id}/block/"
        )
        delete_response = self.client.delete(
            f"/api/users/{self.superadmin.id}/"
        )

        self.assertEqual(block_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_user_returns_204(self):
        self.authenticate(self.superadmin)

        response = self.client.delete(
            f"/api/users/{self.target.id}/",
            {"replacement_user_id": str(self.admin.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        target = User.objects.get(id=self.target.id)
        self.assertIsNotNone(target.deleted_at)
        self.assertFalse(target.is_active)

    def test_delete_user_requires_replacement_user(self):
        self.authenticate(self.superadmin)

        response = self.client.delete(
            f"/api/users/{self.target.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        target = User.objects.get(id=self.target.id)
        self.assertIsNone(target.deleted_at)
        self.assertTrue(target.is_active)

    def test_delete_user_returns_404_for_missing_user(self):
        self.authenticate(self.superadmin)

        response = self.client.delete(
            f"/api/users/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_current_user_endpoint_remains_available(self):
        self.authenticate(self.superadmin)

        response = self.client.get("/api/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.superadmin.id))
        self.assertEqual(response.data["role"], User.Role.SUPERADMIN)


class UserManagementPresentationSerializerTests(TestCase):
    def test_update_serializer_does_not_accept_protected_fields(self):
        from src.modules.users.presentation.api.serializers.update_user import (
            UpdateUserSerializer,
        )

        serializer = UpdateUserSerializer(
            data={
                "password": "newpassword",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)
