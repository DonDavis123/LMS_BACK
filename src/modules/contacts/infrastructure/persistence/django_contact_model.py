import uuid

from django.conf import settings
from django.db import models

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)


class DjangoContactModel(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Relationships
    account = models.ForeignKey(
        DjangoAccountModel,
        on_delete=models.PROTECT,
        related_name="contacts",
        null=True,
        blank=True,
    )

    contact_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_contacts",
    )

    # Contact information
    name = models.CharField(
        max_length=255,
    )

    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
    )

    secondary_email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    other_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    mobile = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    home_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    assistant_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    # Professional information
    title = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    department = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    lead_source = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    vendor_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    # Personal information
    date_of_birth = models.DateField(
        blank=True,
        null=True,
    )

    assistant = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    email_opt_out = models.BooleanField(
        default=False,
    )

    reporting_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="direct_reports",
    )

    # Address
    mailing_address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    mailing_city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    mailing_state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    mailing_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    mailing_postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    other_address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    # Description
    description = models.TextField(
        blank=True,
        null=True,
    )

    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_contacts",
    )

    created_at = models.DateTimeField()

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="modified_contacts",
    )

    updated_at = models.DateTimeField()

    class Meta:
        db_table = "contacts"

    def __str__(self):
        return self.name