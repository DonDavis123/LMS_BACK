from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GoogleOAuthState:
    """What a verified OAuth ``state`` value carries."""

    user_id: UUID
    company_id: UUID


@dataclass(frozen=True)
class GoogleTokenResponse:
    access_token: str
    refresh_token: str | None
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class GoogleAccessToken:
    access_token: str
    google_email: str
