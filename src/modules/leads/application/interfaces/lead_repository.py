from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.leads.domain.entities.lead import Lead
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class LeadRepository(ABC):

    @abstractmethod
    def save(self, lead: Lead) -> Lead:
        pass

    @abstractmethod
    def get_by_id(self, lead_id: UUID) -> Lead | None:
        pass

    @abstractmethod
    def get_all(self) -> list[Lead]:
        pass

    @abstractmethod
    def get_all_with_owner(self, query: ListQuery) -> PaginatedResult[tuple[Lead, str]]:
        pass
    
    @abstractmethod
    def get_by_id_with_owner(
      self,
      lead_id: UUID,
    ) -> tuple[Lead, str] | None:
      pass