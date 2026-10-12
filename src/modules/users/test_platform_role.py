from datetime import datetime, timezone
from uuid import uuid4

from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.shared.tests.tenancy.factories import default_test_company
from src.modules.users.domain.entities.role import MANAGEABLE_ROLES, UserRole
from src.modules.users.domain.entities.user import User as DomainUser
from src.modules.users.infrastructure.persistence.current_user_reader import (
    DjangoCurrentUserReader,
)
from src.modules.users.infrastructure.persistence.models import User
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


class PlatformSuperadminRoleTests(SimpleTestCase):

    def test_role_exists(self):
        self.assertEqual(
            UserRole.PLATFORM_SUPERADMIN.value,
            "PLATFORM_SUPERADMIN",
        )
        self.assertEqual(UserRole("PLATFORM_SUPERADMIN"), UserRole.PLATFORM_SUPERADMIN)

    def test_role_is_not_manageable(self):
        self.assertNotIn(UserRole.PLATFORM_SUPERADMIN, MANAGEABLE_ROLES)

    def test_model_and_domain_roles_match(self):
        self.assertEqual(
            {role.value for role in UserRole},
            {value for value, _ in User.Role.choices},
        )


class PlatformSuperadminApiTests(APITestCase):

    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="superadmin@example.com",
            password="password123",
            name="Super Admin",
            role=User.Role.SUPERADMIN,
            company=default_test_company(),
        )
        self.target = User.objects.create_user(
            email="target@example.com",
            password="password123",
            name="Target User",
            role=User.Role.ADMIN,
            company=default_test_company(),
        )
        self.client.force_authenticate(self.superadmin)

    def test_create_user_rejects_platform_superadmin(self):
        response = self.client.post(
            "/api/users/",
            {
                "name": "Platform",
                "email": "platform@example.com",
                "password": "newpassword123",
                "role": "PLATFORM_SUPERADMIN",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.assertFalse(User.objects.filter(email="platform@example.com").exists())

    def test_update_user_rejects_platform_superadmin(self):
        response = self.client.patch(
            f"/api/users/{self.target.id}/",
            {"role": "PLATFORM_SUPERADMIN"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ADMIN)


class UserCompanyMappingTests(TestCase):

    def test_repository_maps_company_id(self):
        company = DjangoCompanyModel.objects.create(name="Acme", slug="acme")
        with_company = User.objects.create_user(
            email="member@example.com",
            password="password123",
            name="Member",
            role=User.Role.ADMIN,
            company=company,
        )
        without_company = User.objects.create_user(
            email="platform@example.com",
            password="password123",
            name="Platform",
            role=User.Role.PLATFORM_SUPERADMIN,
        )
        member = DjangoUserRepository(company_id=company.id).get_by_id(with_company.id)
        # A company-scoped repository never sees users without a company;
        # the unscoped current-user reader resolves them by their own id.
        platform = DjangoCurrentUserReader().get_by_id(without_company.id)

        self.assertEqual(member.company_id, company.id)
        self.assertIsNone(platform.company_id)
        self.assertEqual(platform.role, UserRole.PLATFORM_SUPERADMIN)

    def test_users_created_through_the_repository_get_the_repository_company(self):
        company = DjangoCompanyModel.objects.create(name="Acme", slug="acme")
        now = datetime.now(timezone.utc)
        domain_user = DomainUser(
            id=uuid4(),
            name="New",
            email="new@example.com",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        created = DjangoUserRepository(company_id=company.id).create(
            domain_user, "password123",
        )

        # The entity carries no company; the repository stamps its own.
        self.assertIsNone(domain_user.company_id)
        self.assertEqual(created.company_id, company.id)
