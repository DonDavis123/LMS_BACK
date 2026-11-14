from abc import ABC, abstractmethod

from src.modules.google_integration.application.dto.oauth import GoogleTokenResponse


class GoogleOAuthClient(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def build_authorization_url(self, state: str, login_hint: str | None = None) -> str:
        pass

    @abstractmethod
    def exchange_code(self, code: str) -> GoogleTokenResponse:
        pass

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> str:
        """Return a fresh access token.

        Raises ``GoogleInvalidGrantError`` when the refresh token is dead.
        """
        pass

    @abstractmethod
    def fetch_account_email(self, access_token: str) -> str:
        pass

    @abstractmethod
    def revoke_token(self, token: str) -> None:
        """Best effort: never raises."""
        pass
