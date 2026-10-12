import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class DjangoCompanyModel(models.Model):

    class Status(models.TextChoices):
        ONBOARDING = "ONBOARDING", "Onboarding"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
    )

    slug = models.SlugField(
        max_length=100,
    )

    website = models.URLField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONBOARDING,
        db_index=True,
    )

    status_reason = models.TextField(
        blank=True,
    )

    status_changed_at = models.DateTimeField(
        null=True,
    )

    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "companies"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("slug"),
                name="company_slug_lower_unique",
            ),
        ]

    def __str__(self):
        return self.name
