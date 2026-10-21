from src.modules.calls.application.dto.get_call import GetCallDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetCallsUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
    ):
        self.call_repository = call_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetCallDTO]:
        return self.call_repository.get_all_with_relations(query)
