from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from src.modules.shared.tests.tenancy.factories import make_company, make_user
from src.modules.users.infrastructure.persistence.models import User


def run(*args, **kwargs):
    out = StringIO()
    call_command("create_platform_admin", *args, stdout=out, **kwargs)
    return out.getvalue()


class CreatePlatformAdminCommandTests(TestCase):

    def test_creates_platform_admin(self):
        run(email="Root@Example.com", name="Root", password="a-strong-pass-1")

        user = User.objects.get(email="root@example.com")
        self.assertEqual(user.role, User.Role.PLATFORM_SUPERADMIN)
        self.assertIsNone(user.company_id)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("a-strong-pass-1"))

    def test_is_idempotent(self):
        run(email="root@example.com", name="Root", password="a-strong-pass-1")

        output = run(email="ROOT@example.com", name="Other", password="another-pass-2")

        self.assertIn("already exists", output)
        self.assertEqual(User.objects.filter(email__iexact="root@example.com").count(), 1)
        user = User.objects.get(email="root@example.com")
        self.assertEqual(user.name, "Root")
        self.assertTrue(user.check_password("a-strong-pass-1"))

    def test_does_not_promote_existing_company_user(self):
        company_user = make_user(make_company(), role=User.Role.ADMIN, email="bob@example.com")

        output = run(email="bob@example.com", name="Bob", password="a-strong-pass-1")

        self.assertIn("already exists", output)
        company_user.refresh_from_db()
        self.assertEqual(company_user.role, User.Role.ADMIN)
        self.assertIsNotNone(company_user.company_id)

    def test_rejects_weak_password(self):
        for password in ("short", "12345678", "password"):
            with self.subTest(password=password):
                with self.assertRaises(CommandError):
                    run(email="root@example.com", name="Root", password=password)
        self.assertFalse(User.objects.filter(email="root@example.com").exists())

    def test_rejects_missing_password(self):
        with patch(
            "src.modules.users.management.commands.create_platform_admin.getpass",
            return_value="",
        ):
            with self.assertRaises(CommandError):
                run(email="root@example.com", name="Root")
        self.assertFalse(User.objects.filter(email="root@example.com").exists())

    def test_prompts_when_password_omitted(self):
        with patch(
            "src.modules.users.management.commands.create_platform_admin.getpass",
            return_value="a-strong-pass-1",
        ):
            run(email="root@example.com", name="Root")

        self.assertTrue(
            User.objects.get(email="root@example.com").check_password("a-strong-pass-1")
        )
