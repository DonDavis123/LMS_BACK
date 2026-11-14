from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from src.modules.google_integration.application.errors import (
    GoogleIntegrationNotConfiguredError,
)
from src.modules.google_integration.application.interfaces.token_cipher import TokenCipher


class FernetTokenCipher(TokenCipher):
    """Encrypts tokens at rest with the ``GOOGLE_TOKEN_ENCRYPTION_KEY`` Fernet key."""

    def _fernet(self) -> Fernet:
        key = (getattr(settings, "GOOGLE_TOKEN_ENCRYPTION_KEY", "") or "").strip()
        if not key:
            raise GoogleIntegrationNotConfiguredError(
                "GOOGLE_TOKEN_ENCRYPTION_KEY is not set."
            )
        try:
            return Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise GoogleIntegrationNotConfiguredError(
                "GOOGLE_TOKEN_ENCRYPTION_KEY is not a valid Fernet key."
            ) from exc

    def encrypt(self, plain_text: str) -> str:
        return self._fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        try:
            return self._fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise GoogleIntegrationNotConfiguredError(
                "Stored Google token cannot be decrypted with the current "
                "GOOGLE_TOKEN_ENCRYPTION_KEY."
            ) from exc
