from src.modules.accounts.application.use_cases.create_account import (
    CreateAccountUseCase,
)
from src.modules.accounts.application.use_cases.get_accounts import (
    GetAccountsUseCase,
)
from src.modules.accounts.application.use_cases.get_account_details import (
    GetAccountDetailsUseCase,
)
from src.modules.accounts.application.use_cases.update_account import (
    UpdateAccountUseCase,
)
from src.modules.accounts.application.use_cases.delete_account import (
    DeleteAccountUseCase,
)

from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)

from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)

from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
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
    contact_repository = DjangoContactRepository()

    return GetAccountDetailsUseCase(
        account_repository=account_repository,
        contact_repository=contact_repository,
    )


def get_update_account_use_case() -> UpdateAccountUseCase:
    account_repository = DjangoAccountRepository()

    return UpdateAccountUseCase(
        account_repository=account_repository,
    )


def get_delete_account_use_case() -> DeleteAccountUseCase:
    account_repository = DjangoAccountRepository()
    contact_repository = DjangoContactRepository()
    transaction_manager = DjangoTransactionManager()

    return DeleteAccountUseCase(
        account_repository=account_repository,
        contact_repository=contact_repository,
        transaction_manager=transaction_manager,
    )
