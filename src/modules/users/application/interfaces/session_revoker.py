from abc import ABC, abstractmethod
from uuid import UUID


class SessionRevoker(ABC):

    @abstractmethod
    def revoke_all_sessions(self, user_id: UUID) -> None:
        """Invalidate every refresh token issued to the user."""
        pass
