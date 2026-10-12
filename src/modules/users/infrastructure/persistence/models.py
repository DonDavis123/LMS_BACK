import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Superadmin"
        ADMIN = "ADMIN", "Admin"
        SALES_MANAGER = "SALES_MANAGER", "Sales Manager"
        SALES_EXECUTIVE = "SALES_EXECUTIVE", "Sales Executive"
        PLATFORM_SUPERADMIN = "PLATFORM_SUPERADMIN", "Platform Superadmin"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=150,
    )

    email = models.EmailField(
        unique=True,
        db_index=True,
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.ADMIN,
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_staff = models.BooleanField(
        default=False,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="user_email_lower_unique",
            ),
        ]

    def __str__(self):
        return self.email