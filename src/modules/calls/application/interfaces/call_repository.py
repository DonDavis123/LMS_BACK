from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.calls.application.dto.get_call import GetCallDTO
from src.modules.calls.domain.entities.call import Call
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class CallRepository(ABC):

    @abstractmethod
    def save(self, call: Call) -> Call:
        pass

    @abstractmethod
    def get_by_id(self, call_id: UUID) -> Call | None:
        pass

    @abstractmethod
    def get_by_id_with_relations(self, call_id: UUID) -> GetCallDTO | None:
        pass

    @abstractmethod
    def get_all_with_relations(self, query: ListQuery) -> PaginatedResult[GetCallDTO]:
        pass

    @abstractmethod
    def get_by_related_record(
        self,
        *,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
        exclude_call_id: UUID | None = None,
        limit: int = 50,
    ) -> list[GetCallDTO]:
        """Return active calls of one lead OR contact, newest first."""
        pass

    @abstractmethod
    def count_by_related_record(
        self,
        *,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
    ) -> int:
        """Count active calls of one lead OR contact."""
        pass

    @abstractmethod
    def soft_delete_by_lead_id(self, lead_id: UUID) -> list[UUID]:
        """Soft delete the lead's calls and return the deleted call ids."""
        pass

    @abstractmethod
    def soft_delete_by_contact_id(self, contact_id: UUID) -> list[UUID]:
        """Soft delete the contact's calls and return the deleted call ids."""
        pass

    @abstractmethod
    def soft_delete_by_account_id(self, account_id: UUID) -> list[UUID]:
        """Soft delete the account's calls and return the deleted call ids."""
        pass

    @abstractmethod
    def unlink_account_from_contact_calls(self, account_id: UUID) -> None:
        pass

    @abstractmethod
    def delete_by_owner_id(self, owner_id: UUID) -> int:
        """Permanently delete every Call owned by ``owner_id``."""
        pass

    @abstractmethod
    def count_by_owner_id(self, owner_id: UUID) -> int:
        pass
