from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from src.modules.shared.presentation.permissions import (
    IsCompanyUser,
    IsPlatformSuperAdmin,
)
from src.modules.shared.tests.tenancy.factories import make_company


def fake_user(role="ADMIN", company_id="unset", is_active=True):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        is_active=is_active,
        is_authenticated=True,
        company_id=make_company().id if company_id == "unset" else company_id,
    )


def check(permission_class, user):
    return permission_class().has_permission(SimpleNamespace(user=user), None)


class IsCompanyUserTests(TestCase):

    def test_company_user_is_allowed(self):
        for role in ("SUPERADMIN", "ADMIN", "SALES_MANAGER", "SALES_EXECUTIVE"):
            with self.subTest(role=role):
                self.assertTrue(check(IsCompanyUser, fake_user(role=role)))

    def test_platform_superadmin_is_denied(self):
        self.assertFalse(
            check(IsCompanyUser, fake_user(role="PLATFORM_SUPERADMIN", company_id=None))
        )
        self.assertFalse(
            check(IsCompanyUser, fake_user(role="PLATFORM_SUPERADMIN"))
        )

    def test_inactive_user_is_denied(self):
        self.assertFalse(check(IsCompanyUser, fake_user(is_active=False)))

    def test_user_without_company_is_denied(self):
        self.assertFalse(check(IsCompanyUser, fake_user(company_id=None)))

    def test_anonymous_is_denied(self):
        self.assertFalse(check(IsCompanyUser, AnonymousUser()))

    def test_missing_user_is_denied(self):
        self.assertFalse(check(IsCompanyUser, None))


class IsPlatformSuperAdminTests(TestCase):

    def test_platform_superadmin_is_allowed(self):
        self.assertTrue(
            check(IsPlatformSuperAdmin, fake_user(role="PLATFORM_SUPERADMIN", company_id=None))
        )

    def test_company_users_are_denied(self):
        for role in ("SUPERADMIN", "ADMIN", "SALES_MANAGER", "SALES_EXECUTIVE"):
            with self.subTest(role=role):
                self.assertFalse(check(IsPlatformSuperAdmin, fake_user(role=role)))

    def test_inactive_platform_superadmin_is_denied(self):
        self.assertFalse(
            check(
                IsPlatformSuperAdmin,
                fake_user(role="PLATFORM_SUPERADMIN", company_id=None, is_active=False),
            )
        )

    def test_anonymous_is_denied(self):
        self.assertFalse(check(IsPlatformSuperAdmin, AnonymousUser()))

    def test_missing_user_is_denied(self):
        self.assertFalse(check(IsPlatformSuperAdmin, None))
