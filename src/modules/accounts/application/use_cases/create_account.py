from src.modules.accounts.application.dto.create_account_dto import (
    CreateAccountDTO,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account


class CreateAccountUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
    ):
        self.account_repository = account_repository

    def execute(
        self,
        data: CreateAccountDTO,
        current_user_id,
    ) -> Account:

        account_owner_id = (
            data.account_owner_id
            or current_user_id
        )

        account = Account.create(
            account_owner_id=account_owner_id,
            account_name=data.account_name,
            account_site=data.account_site,
            account_number=data.account_number,
            account_type=data.account_type,
            industry=data.industry,
            annual_revenue=data.annual_revenue,
            rating=data.rating,
            phone=data.phone,
            website=data.website,
            ticker_symbol=data.ticker_symbol,
            ownership=data.ownership,
            employees=data.employees,
            sic_code=data.sic_code,

            # Billing information
            billing_address=data.billing_address,
            billing_city=data.billing_city,
            billing_state=data.billing_state,
            billing_country=data.billing_country,
            billing_postal_code=data.billing_postal_code,

            # Description
            description=data.description,

            created_by_id=current_user_id,
        )

        return self.account_repository.save(account)