import uuid

from django.conf import settings
from django.db import models

from src.modules.google_integration.domain.enums.google_connection_status import (
    GoogleConnectionStatus,
)


class DjangoGoogleConnectionModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_connection",
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    google_email = models.EmailField()

    # Fernet-encrypted; the plain token is never stored.
    refresh_token_encrypted = models.TextField()

    scopes = models.TextField(
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=16,
        choices=[(item.value, item.value) for item in GoogleConnectionStatus],
        default=GoogleConnectionStatus.CONNECTED.value,
    )

    connected_at = models.DateTimeField()

    updated_at = models.DateTimeField()

    revoked_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "google_connections"

    def __str__(self):
        return f"{self.user_id} -> {self.google_email}"
