from uuid import UUID

from src.modules.deals.application.dto.get_deal import GetDealDTO
from src.modules.deals.application.interfaces.deal_repository import DealRepository


class GetDealUseCase:

    def __init__(self, deal_repository: DealRepository):
        self.deal_repository = deal_repository

    def execute(self, deal_id: UUID) -> GetDealDTO | None:
        return self.deal_repository.get_by_id_with_relations(deal_id)
