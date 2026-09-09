from uuid import UUID

from src.modules.accounts.application.dto.account_details_dto import (
    GetAccountDetailsDTO,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)


class GetAccountDetailsUseCase:
    def __init__(self, account_repository: AccountRepository):
        self.account_repository = account_repository

    def execute(
        self,
        account_id: UUID,
    ) -> GetAccountDetailsDTO | None:

        result = self.account_repository.get_by_id_with_owner(
            account_id=account_id,
        )

        if result is None:
            return None

        account, account_owner_name = result

        return GetAccountDetailsDTO(
            id=account.id,

            account_owner_id=account.account_owner_id,
            account_owner_name=account_owner_name,

            account_name=account.account_name,
            account_site=account.account_site,
            account_number=account.account_number,
            account_type=account.account_type,
            industry=account.industry,
            annual_revenue=account.annual_revenue,
            rating=account.rating,
            phone=account.phone,
            website=account.website,
            ticker_symbol=account.ticker_symbol,
            ownership=account.ownership,
            employees=account.employees,
            sic_code=account.sic_code,

            billing_address=account.billing_address,
            billing_city=account.billing_city,
            billing_state=account.billing_state,
            billing_country=account.billing_country,
            billing_postal_code=account.billing_postal_code,

            description=account.description,

            created_by_id=account.created_by_id,
            created_at=account.created_at,

            modified_by_id=account.modified_by_id,
            updated_at=account.updated_at,
        )