from src.modules.accounts.application.use_cases.create_account import (
    CreateAccountUseCase,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)


def get_create_account_use_case() -> CreateAccountUseCase:
    account_repository = DjangoAccountRepository()

    return CreateAccountUseCase(
        account_repository=account_repository,
    )