from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.deals.application.dto.deal_board import (
    DealBoardColumnDTO,
    DealBoardQuery,
)
from src.modules.deals.application.dto.deal_forecast import DealForecastDTO
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

    @abstractmethod
    def get_board(
        self,
        query: DealBoardQuery,
        closed_since: datetime,
        card_limit: int,
    ) -> list[DealBoardColumnDTO]:
        """Every stage as a column, in stage order.

        Won / Lost deals only count when ``closed_at >= closed_since``.
        """
        pass

    @abstractmethod
    def get_forecast(
        self,
        owner_id: UUID | None,
        month_start: datetime,
        month_end: datetime,
    ) -> DealForecastDTO:
        """Open pipeline, weighted forecast and Won / Lost totals for the
        window ``month_start <= closed_at < month_end``."""
        pass
