from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.google_integration.application.dto.oauth import GoogleOAuthState


class OAuthStateSigner(ABC):
    @abstractmethod
    def sign(self, user_id: UUID, company_id: UUID) -> str:
        pass

    @abstractmethod
    def verify(self, state: str) -> GoogleOAuthState:
        """Raises ``GoogleOAuthStateError`` when forged, malformed or expired."""
        pass
