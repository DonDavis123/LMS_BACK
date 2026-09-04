import uuid

from django.db import models


class DjangoLeadModel(models.Model):

    class BusinessType(models.TextChoices):
        B2B = "B2B", "B2B"
        B2C = "B2C", "B2C"
        ONE_S_ACADEMY = "OneS Academy", "OneS Academy"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    lead_generator = models.CharField(
        max_length=150,
    )

    client_partner_name = models.CharField(
        max_length=255,
    )

    mobile_number = models.CharField(
        max_length=20,
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    city_location = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    business_type = models.CharField(
        max_length=30,
        choices=BusinessType.choices,
    )

    lead_source = models.CharField(
        max_length=100,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "leads"

    def __str__(self):
        return self.client_partner_name