import uuid

from django.conf import settings
from django.db import models


class DjangoAccountModel(models.Model):

    class Ownership(models.TextChoices):
        NONE = "None", "None"
        OTHER = "Other", "Other"
        PRIVATE = "Private", "Private"
        PUBLIC = "Public", "Public"
        SUBSIDIARY = "Subsidiary", "Subsidiary"
        PARTNERSHIP = "Partnership", "Partnership"
        GOVERNMENT = "Government", "Government"
        PRIVATELY_HELD = "Privately Held", "Privately Held"
        PUBLIC_COMPANY = "Public Company", "Public Company"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Account ownership
    account_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_accounts",
    )

    account_name = models.CharField(max_length=255)
    account_site = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    account_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    account_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    industry = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )
    annual_revenue = models.BigIntegerField(
        blank=True,
        null=True,
    )
    rating = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    website = models.URLField(
        max_length=500,
        blank=True,
        null=True,
    )
    ticker_symbol = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )
    ownership = models.CharField(
        max_length=50,
        choices=Ownership.choices,
        default=Ownership.NONE,
    )
    employees = models.PositiveIntegerField(
        blank=True,
        null=True,
    )
    sic_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    # Billing address
    billing_address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )
    billing_city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    billing_state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    billing_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    billing_postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_accounts",
    )
    created_at = models.DateTimeField()

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="modified_accounts",
    )
    updated_at = models.DateTimeField()

    # Soft delete
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts"

    def __str__(self):
        return self.account_name
