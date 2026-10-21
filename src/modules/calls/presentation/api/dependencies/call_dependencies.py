from src.modules.shared.application.tenant_context import TenantContext
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.calls.application.use_cases.create_call import CreateCallUseCase
from src.modules.calls.application.use_cases.delete_call import DeleteCallUseCase
from src.modules.calls.application.use_cases.get_call import GetCallDetailUseCase
from src.modules.calls.application.use_cases.get_call_record_history import GetCallRecordHistoryUseCase
from src.modules.calls.application.use_cases.get_call_records import GetCallRecordsUseCase
from src.modules.calls.application.use_cases.get_calls import GetCallsUseCase
from src.modules.calls.application.use_cases.update_call import UpdateCallUseCase
from src.modules.calls.infrastructure.persistence.django_call_repository import DjangoCallRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def transaction_manager():
    return DjangoTransactionManager()


def get_create_call_use_case(ctx: TenantContext) -> CreateCallUseCase:
    return CreateCallUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoLeadRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )


def get_call_detail_use_case(ctx: TenantContext) -> GetCallDetailUseCase:
    return GetCallDetailUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
    )


def get_calls_use_case(ctx: TenantContext) -> GetCallsUseCase:
    return GetCallsUseCase(DjangoCallRepository(company_id=ctx.company_id))


def get_call_records_use_case(ctx: TenantContext) -> GetCallRecordsUseCase:
    return GetCallRecordsUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
    )


def get_call_record_history_use_case(ctx: TenantContext) -> GetCallRecordHistoryUseCase:
    return GetCallRecordHistoryUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
    )


def get_update_call_use_case(ctx: TenantContext) -> UpdateCallUseCase:
    return UpdateCallUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )


def get_delete_call_use_case(ctx: TenantContext) -> DeleteCallUseCase:
    return DeleteCallUseCase(
        DjangoCallRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )
