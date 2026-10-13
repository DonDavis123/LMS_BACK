from src.modules.shared.application.tenant_context import TenantContext
from src.modules.accounts.application.use_cases.create_account import CreateAccountUseCase
from src.modules.accounts.application.use_cases.get_accounts import GetAccountsUseCase
from src.modules.accounts.application.use_cases.get_account_details import GetAccountDetailsUseCase
from src.modules.accounts.application.use_cases.update_account import UpdateAccountUseCase
from src.modules.accounts.application.use_cases.delete_account import DeleteAccountUseCase
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def get_create_account_use_case(ctx: TenantContext) -> CreateAccountUseCase:
    return CreateAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(),
        DjangoTransactionManager(),
        DjangoUserRepository(company_id=ctx.company_id),
    )


def get_accounts_use_case(ctx: TenantContext) -> GetAccountsUseCase:
    return GetAccountsUseCase(DjangoAccountRepository(company_id=ctx.company_id))


def get_account_details_use_case(ctx: TenantContext) -> GetAccountDetailsUseCase:
    return GetAccountDetailsUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
    )


def get_update_account_use_case(ctx: TenantContext) -> UpdateAccountUseCase:
    return UpdateAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(),
        DjangoTransactionManager(),
    )
def get_delete_account_use_case(ctx: TenantContext) -> DeleteAccountUseCase:
    return DeleteAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoTaskRepository(),
        DjangoTimelineRepository(),
        DjangoTransactionManager(),
    )
