from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password

from src.modules.users.infrastructure.persistence.models import User


class Command(BaseCommand):
    help = (
        "Create the first PLATFORM_SUPERADMIN (no company). Idempotent: if the "
        "email already exists nothing is changed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument(
            "--password",
            help="Omit to be prompted securely.",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        name = (options["name"] or "").strip()

        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("A valid --email is required.")
        if not name:
            raise CommandError("--name is required.")

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(
                f"A user with email {email} already exists. No changes made."
            )
            return

        password = options.get("password")
        if password is None:
            password = getpass("Password: ")
            confirm = getpass("Password (again): ")
            if password != confirm:
                raise CommandError("Passwords do not match.")

        if not password:
            raise CommandError("A password is required.")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters long.")
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("Weak password: " + " ".join(error.messages))

        User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=User.Role.PLATFORM_SUPERADMIN,
            company=None,
            is_active=True,
            is_staff=False,
        )
        self.stdout.write(self.style.SUCCESS(f"Platform admin {email} created."))
