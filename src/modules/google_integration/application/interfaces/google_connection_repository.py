from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.google_integration.domain.entities.google_connection import GoogleConnection


class GoogleConnectionRepository(ABC):
    @abstractmethod
    def get_by_user_id(self, user_id: UUID) -> GoogleConnection | None:
        pass

    @abstractmethod
    def save(self, connection: GoogleConnection) -> GoogleConnection:
        """Insert or update the single connection of ``connection.user_id``."""
        pass

    @abstractmethod
    def delete_by_user_id(self, user_id: UUID) -> bool:
        pass
