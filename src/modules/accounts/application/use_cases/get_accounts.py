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
                    account_number=account.account_number,
                    account_type=account.account_type,
                    industry=account.industry,
                    rating=account.rating,
                    employees=account.employees,
                    annual_revenue=account.annual_revenue,
                    billing_address=account.billing_address,
                    billing_city=account.billing_city,
                    billing_state=account.billing_state,
                    billing_country=account.billing_country,
                    billing_postal_code=account.billing_postal_code,
                    created_at=account.created_at,
                    updated_at=account.updated_at,
                )
                for account, account_owner_name in result.results
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )
