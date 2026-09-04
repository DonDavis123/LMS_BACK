from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.users.domain.entities.user import User


class UserRepository(ABC):

    @abstractmethod
    def create(self, user: User, password: str) -> User:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None:
        pass