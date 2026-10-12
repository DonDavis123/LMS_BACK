from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from src.modules.shared.tests.tenancy.factories import default_test_company
from src.modules.users.infrastructure.persistence.models import User


def run_check_duplicate_emails():
    """Return (exit code, printed output) of check_duplicate_emails."""
    out = StringIO()
    try:
        call_command("check_duplicate_emails", stdout=out)
    except SystemExit as exc:
        return exc.code, out.getvalue()
    return 0, out.getvalue()


def make_user(email):
    return User.objects.create_user(company=default_test_company(),
        email=email,
        password="password123",
        name=email.split("@")[0],
        role=User.Role.ADMIN,
    )


class CheckDuplicateEmailsTests(TestCase):

    def test_clean_database_exits_zero(self):
        make_user("a@example.com")
        make_user("b@example.com")

        code, output = run_check_duplicate_emails()

        self.assertEqual(code, 0, output)
        self.assertIn("No case-insensitive duplicate emails", output)

    def test_database_constraint_blocks_case_different_duplicates(self):
        make_user("dup@example.com")

        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user("DUP@example.com")

    def test_case_different_duplicate_exits_one(self):
        # Bypass the constraint (as it would be on a database that has not
        # been migrated yet) so a duplicate can be created.
        constraint = next(
            c for c in User._meta.constraints if c.name == "user_email_lower_unique"
        )
        with connection.schema_editor() as schema_editor:
            schema_editor.remove_constraint(User, constraint)

        first = make_user("dup@example.com")
        second = make_user("DUP@example.com")
        make_user("unique@example.com")

        code, output = run_check_duplicate_emails()

        self.assertEqual(code, 1, output)
        self.assertIn("dup@example.com", output)
        self.assertIn(str(first.id), output)
        self.assertIn(str(second.id), output)
        self.assertNotIn("unique@example.com", output)
