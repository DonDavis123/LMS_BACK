from src.modules.accounts.application.dto.get_accounts import (
    GetAccountsDTO,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)


class GetAccountsUseCase:
    def __init__(self, account_repository: AccountRepository):
        self.account_repository = account_repository

    def execute(self) -> list[GetAccountsDTO]:
        accounts = self.account_repository.get_all_with_owner()

        return [
            GetAccountsDTO(
                id=account.id,
                account_name=account.account_name,
                phone=account.phone,
                website=account.website,
                account_owner_id=account.account_owner_id,
                account_owner_name=account_owner_name,
            )
            for account, account_owner_name in accounts
        ]