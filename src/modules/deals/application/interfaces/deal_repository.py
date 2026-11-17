from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.deals.application.dto.get_deal import GetDealDTO
from src.modules.deals.domain.entities.deal import Deal
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class DealRepository(ABC):

    @abstractmethod
    def save(self, deal: Deal) -> Deal:
        pass

    @abstractmethod
    def get_by_id(self, deal_id: UUID) -> Deal | None:
        """Return the (non-deleted) deal of the company, or None."""
        pass

    @abstractmethod
    def get_by_id_with_relations(self, deal_id: UUID) -> GetDealDTO | None:
        pass

    @abstractmethod
    def get_all_with_relations(self, query: ListQuery) -> PaginatedResult[GetDealDTO]:
        pass
