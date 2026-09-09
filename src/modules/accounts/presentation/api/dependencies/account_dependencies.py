from src.modules.accounts.application.use_cases.create_account import (
    CreateAccountUseCase,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.accounts.application.use_cases.get_accounts import (
    GetAccountsUseCase,
)
from src.modules.accounts.application.use_cases.get_account_details import (
    GetAccountDetailsUseCase,
)


def get_create_account_use_case() -> CreateAccountUseCase:
    account_repository = DjangoAccountRepository()

    return CreateAccountUseCase(
        account_repository=account_repository,
    )

def get_accounts_use_case() -> GetAccountsUseCase:
    account_repository = DjangoAccountRepository()

    return GetAccountsUseCase(
        account_repository=account_repository,
    )

def get_account_details_use_case() -> GetAccountDetailsUseCase:
    account_repository = DjangoAccountRepository()

    return GetAccountDetailsUseCase(
        account_repository=account_repository,
    )