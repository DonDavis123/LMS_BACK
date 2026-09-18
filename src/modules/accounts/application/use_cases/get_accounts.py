from src.modules.accounts.application.dto.get_accounts import GetAccountsDTO
from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetAccountsUseCase:
    def __init__(self, account_repository: AccountRepository):
        self.account_repository = account_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetAccountsDTO]:
        result = self.account_repository.get_all_with_owner(query)

        return PaginatedResult(
            results=[
                GetAccountsDTO(
                    id=account.id,
                    account_name=account.account_name,
                    phone=account.phone,
                    website=account.website,
                    account_owner_id=account.account_owner_id,
                    account_owner_name=account_owner_name,
                )
                for account, account_owner_name in result.results
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )
