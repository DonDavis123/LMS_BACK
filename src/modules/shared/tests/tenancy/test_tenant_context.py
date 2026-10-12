from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.presentation.tenant import get_tenant_context


def fake_user(role="ADMIN", company_id="unset", is_active=True):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        is_active=is_active,
        is_authenticated=True,
        company_id=uuid4() if company_id == "unset" else company_id,
    )


def request_for(user):
    return SimpleNamespace(user=user)


class TenantContextTests(SimpleTestCase):

    def test_context_is_frozen(self):
        ctx = TenantContext(company_id=uuid4(), user_id=uuid4(), role="ADMIN")

        with self.assertRaises(Exception):
            ctx.company_id = uuid4()

    def test_company_user_gets_context_from_the_user(self):
        for role in ("SUPERADMIN", "ADMIN", "SALES_MANAGER", "SALES_EXECUTIVE"):
            with self.subTest(role=role):
                user = fake_user(role=role)

                ctx = get_tenant_context(request_for(user))

                self.assertEqual(ctx.company_id, user.company_id)
                self.assertEqual(ctx.user_id, user.id)
                self.assertEqual(ctx.role, role)

    def test_platform_superadmin_is_denied(self):
        with self.assertRaises(PermissionDenied):
            get_tenant_context(
                request_for(fake_user(role="PLATFORM_SUPERADMIN", company_id=None))
            )

    def test_platform_superadmin_with_a_company_is_still_denied(self):
        with self.assertRaises(PermissionDenied):
            get_tenant_context(request_for(fake_user(role="PLATFORM_SUPERADMIN")))

    def test_inactive_user_is_denied(self):
        with self.assertRaises(PermissionDenied):
            get_tenant_context(request_for(fake_user(is_active=False)))

    def test_user_without_company_is_denied(self):
        with self.assertRaises(PermissionDenied):
            get_tenant_context(request_for(fake_user(company_id=None)))

    def test_anonymous_user_is_rejected(self):
        with self.assertRaises(NotAuthenticated):
            get_tenant_context(request_for(AnonymousUser()))

    def test_missing_user_is_rejected(self):
        with self.assertRaises(NotAuthenticated):
            get_tenant_context(SimpleNamespace())

    def test_request_data_is_never_used(self):
        user = fake_user()
        request = SimpleNamespace(
            user=user,
            data={"company_id": str(uuid4())},
            query_params={"company_id": str(uuid4())},
            headers={"X-Company-Id": str(uuid4())},
        )

        self.assertEqual(get_tenant_context(request).company_id, user.company_id)
