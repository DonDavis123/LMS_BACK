from src.modules.deals.application.dto.get_deal import GetDealDTO
from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetDealsUseCase:

    def __init__(self, deal_repository: DealRepository):
        self.deal_repository = deal_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetDealDTO]:
        return self.deal_repository.get_all_with_relations(query)
