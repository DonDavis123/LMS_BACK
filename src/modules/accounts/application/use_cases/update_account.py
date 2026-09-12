from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.dto.update_account import UpdateAccountDTO
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)


class UpdateAccountUseCase:
    def __init__(
        self,
        account_repository: AccountRepository,
    ):
        self.account_repository = account_repository

    def execute(
        self,
        data: UpdateAccountDTO,
        current_user_id: UUID,
    ):
        account = self.account_repository.get_by_id(
            data.account_id,
        )

        if account is None:
            raise ValueError("Account not found.")

        if account.is_deleted:
            raise ValueError("Deleted Account cannot be updated.")

        account.account_name = data.account_name
        account.account_site = data.account_site
        account.account_number = data.account_number
        account.account_type = data.account_type
        account.industry = data.industry
        account.annual_revenue = data.annual_revenue
        account.rating = data.rating
        account.phone = data.phone
        account.website = data.website
        account.ticker_symbol = data.ticker_symbol

        if data.ownership is not None:
            account.ownership = data.ownership

        account.employees = data.employees
        account.sic_code = data.sic_code

        account.billing_address = data.billing_address
        account.billing_city = data.billing_city
        account.billing_state = data.billing_state
        account.billing_country = data.billing_country
        account.billing_postal_code = data.billing_postal_code

        account.description = data.description

        # Backend-controlled audit fields
        account.modified_by_id = current_user_id
        account.updated_at = datetime.now(timezone.utc)

        return self.account_repository.save(account)