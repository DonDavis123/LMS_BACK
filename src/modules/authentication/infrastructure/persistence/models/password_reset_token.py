import uuid

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PasswordResetToken(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )

    token_hash = models.CharField(
        max_length=128,
        unique=True,
    )

    expires_at = models.DateTimeField()

    used = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "password_reset_tokens"
        indexes = [
            models.Index(
                fields=["user", "used"],
                name="password_reset_user_used_idx",
            ),
            models.Index(
                fields=["expires_at"],
                name="password_reset_expires_idx",
            ),
        ]

    def is_valid(self) -> bool:
        return (
            not self.used
            and timezone.now() < self.expires_at
        )

    def mark_as_used(self) -> None:
        self.used = True
        self.used_at = timezone.now()

    @classmethod
    def create_expiry(cls):
        return timezone.now() + timedelta(minutes=15)