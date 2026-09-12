import hashlib
import secrets

from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from src.modules.authentication.application.interfaces.password_reset_token import (
    PasswordResetTokenService,
)
from src.modules.authentication.infrastructure.persistence.models.password_reset_token import (
    PasswordResetToken,
)


class DjangoPasswordResetTokenService(PasswordResetTokenService):

    TOKEN_EXPIRY_MINUTES = 15

    @transaction.atomic
    def generate_token(self, user_id: UUID) -> str:
        """
        Generate a secure password reset token.

        Previous unused tokens for the same user are invalidated
        before creating the new token.
        """

        now = timezone.now()

        # Invalidate all previous unused tokens.
        PasswordResetToken.objects.filter(
            user_id=user_id,
            used=False,
        ).update(
            used=True,
            used_at=now,
        )

        # Generate a cryptographically secure random token.
        raw_token = secrets.token_urlsafe(32)

        # Store only the SHA-256 hash in the database.
        token_hash = self._hash_token(raw_token)

        expires_at = now + timedelta(
            minutes=self.TOKEN_EXPIRY_MINUTES,
        )

        PasswordResetToken.objects.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # Return the raw token only to the caller.
        return raw_token

    def validate_token(self, token: str) -> UUID | None:
        """
        Validate a password reset token.

        Returns the associated user ID when valid.
        Returns None when the token is invalid, expired, or used.
        """

        token_hash = self._hash_token(token)

        reset_token = (
            PasswordResetToken.objects
            .filter(token_hash=token_hash)
            .first()
        )

        if reset_token is None:
            return None

        if not reset_token.is_valid():
            return None

        return reset_token.user_id

    @transaction.atomic
    def consume_token(self, token: str) -> None:
        """
        Mark a valid password reset token as used.

        Once consumed, the token cannot be used again.
        """

        token_hash = self._hash_token(token)

        reset_token = (
            PasswordResetToken.objects
            .select_for_update()
            .filter(token_hash=token_hash)
            .first()
        )

        if reset_token is None:
            raise ValueError("Invalid password reset token.")

        if not reset_token.is_valid():
            raise ValueError(
                "Password reset token is expired or already used."
            )

        reset_token.mark_as_used()
        reset_token.save(
            update_fields=[
                "used",
                "used_at",
            ],
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        """
        Hash the raw reset token using SHA-256.
        """

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()