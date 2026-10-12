import sys

from django.core.management.base import BaseCommand

from src.modules.users.infrastructure.persistence.duplicate_emails import (
    find_duplicate_emails,
)


class Command(BaseCommand):
    help = (
        "List user emails that are duplicated when compared "
        "case-insensitively, with their user ids. "
        "Exits with code 1 if any are found."
    )

    def handle(self, *args, **options):
        duplicates = find_duplicate_emails()

        if not duplicates:
            self.stdout.write(
                self.style.SUCCESS("No case-insensitive duplicate emails found.")
            )
            return

        self.stdout.write(
            self.style.ERROR(
                f"{len(duplicates)} email(s) are duplicated when compared "
                "case-insensitively:"
            )
        )
        for email_lower, users in duplicates.items():
            self.stdout.write(email_lower)
            for user_id, stored_email in users:
                self.stdout.write(f"  {user_id}  {stored_email}")

        sys.exit(1)
