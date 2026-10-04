from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.user import User


class UserRepository(ABC):

    @abstractmethod
    def create(
        self,
        user: User,
        password: str,
    ) -> User:
        pass

    @abstractmethod
    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        pass

    @abstractmethod
    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        pass

    @abstractmethod
    def get_lead_owners(
        self,
        exclude_user_id: UUID | None = None,
    ) -> list[User]:
        pass

    @abstractmethod
    def get_all(
        self,
        query: ListQuery,
    ) -> PaginatedResult[User]:
        pass

    @abstractmethod
    def update(
        self,
        user: User,
    ) -> User:
        pass

    @abstractmethod
    def set_active(
        self,
        user_id: UUID,
        is_active: bool,
    ) -> User | None:
        pass

    @abstractmethod
    def set_password(
        self,
        user_id: UUID,
        password: str,
    ) -> User | None:
        pass

    @abstractmethod
    def soft_delete(
        self,
        user_id: UUID,
        deleted_at: datetime,
    ) -> User | None:
        pass
