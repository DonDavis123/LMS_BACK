from src.modules.accounts.application.use_cases.create_account import CreateAccountUseCase
from src.modules.accounts.application.use_cases.get_accounts import GetAccountsUseCase
from src.modules.accounts.application.use_cases.get_account_details import GetAccountDetailsUseCase
from src.modules.accounts.application.use_cases.update_account import UpdateAccountUseCase
from src.modules.accounts.application.use_cases.delete_account import DeleteAccountUseCase
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def get_create_account_use_case() -> CreateAccountUseCase:
    return CreateAccountUseCase(DjangoAccountRepository(), recorder(), DjangoTransactionManager())


def get_accounts_use_case() -> GetAccountsUseCase:
    return GetAccountsUseCase(DjangoAccountRepository())


def get_account_details_use_case() -> GetAccountDetailsUseCase:
    return GetAccountDetailsUseCase(DjangoAccountRepository(), DjangoContactRepository())


def get_update_account_use_case() -> UpdateAccountUseCase:
    return UpdateAccountUseCase(
        DjangoAccountRepository(),
        recorder(),
        DjangoTransactionManager(),
    )
def get_delete_account_use_case() -> DeleteAccountUseCase:
    return DeleteAccountUseCase(DjangoAccountRepository(), DjangoContactRepository(), DjangoTaskRepository(), DjangoTimelineRepository(), DjangoTransactionManager())
