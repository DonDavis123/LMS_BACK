from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.modules.google_integration.domain.enums.google_connection_status import (
    GoogleConnectionStatus,
)


@dataclass
class GoogleConnection:
    """One user's link to their Google account.

    The refresh token is only ever held here in its encrypted form; the
    application layer decrypts it through the ``TokenCipher`` port.
    """

    id: UUID
    user_id: UUID
    company_id: UUID
    google_email: str
    refresh_token_encrypted: str
    scopes: str
    status: GoogleConnectionStatus
    connected_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: UUID,
        company_id: UUID,
        google_email: str,
        refresh_token_encrypted: str,
        scopes: str,
    ) -> "GoogleConnection":
        if not google_email or not google_email.strip():
            raise ValueError("Google account email is required.")
        if not refresh_token_encrypted:
            raise ValueError("Google refresh token is required.")

        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            user_id=user_id,
            company_id=company_id,
            google_email=google_email.strip().lower(),
            refresh_token_encrypted=refresh_token_encrypted,
            scopes=scopes,
            status=GoogleConnectionStatus.CONNECTED,
            connected_at=now,
            updated_at=now,
            revoked_at=None,
        )

    @property
    def is_connected(self) -> bool:
        return self.status == GoogleConnectionStatus.CONNECTED

    def reconnect(
        self,
        google_email: str,
        refresh_token_encrypted: str,
        scopes: str,
    ) -> None:
        if not google_email or not google_email.strip():
            raise ValueError("Google account email is required.")
        if not refresh_token_encrypted:
            raise ValueError("Google refresh token is required.")

        now = datetime.now(timezone.utc)
        self.google_email = google_email.strip().lower()
        self.refresh_token_encrypted = refresh_token_encrypted
        self.scopes = scopes
        self.status = GoogleConnectionStatus.CONNECTED
        self.connected_at = now
        self.updated_at = now
        self.revoked_at = None

    def mark_revoked(self) -> None:
        now = datetime.now(timezone.utc)
        self.status = GoogleConnectionStatus.REVOKED
        self.revoked_at = now
        self.updated_at = now
