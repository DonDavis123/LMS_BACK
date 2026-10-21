from src.modules.shared.application.tenant_context import TenantContext
from src.modules.leads.application.use_cases.create_lead import CreateLeadUseCase
from src.modules.leads.application.use_cases.get_leads import GetLeadsUseCase
from src.modules.leads.application.use_cases.get_leaddetails import GetLeadDetailsUseCase
from src.modules.leads.application.use_cases.update_lead import UpdateLeadUseCase
from src.modules.leads.application.use_cases.delete_lead import DeleteLeadUseCase
from src.modules.leads.application.use_cases.convert_lead import ConvertLeadUseCase
from src.modules.leads.application.use_cases.coversion_check import ConversionCheckUseCase
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.calls.infrastructure.persistence.django_call_repository import DjangoCallRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import DjangoPicklistRepository


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def get_create_lead_use_case(ctx: TenantContext) -> CreateLeadUseCase:
    return CreateLeadUseCase(DjangoLeadRepository(company_id=ctx.company_id), DjangoUserRepository(company_id=ctx.company_id), recorder(ctx), DjangoTransactionManager(), picklist_repository=DjangoPicklistRepository(company_id=ctx.company_id))


def get_update_lead_use_case(ctx: TenantContext) -> UpdateLeadUseCase:
    return UpdateLeadUseCase(
        DjangoLeadRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
        picklist_repository=DjangoPicklistRepository(company_id=ctx.company_id),
    )

def get_leads_use_case(ctx: TenantContext) -> GetLeadsUseCase:
    return GetLeadsUseCase(DjangoLeadRepository(company_id=ctx.company_id))


def get_lead_details_use_case(ctx: TenantContext) -> GetLeadDetailsUseCase:
    return GetLeadDetailsUseCase(DjangoLeadRepository(company_id=ctx.company_id))


def get_delete_lead_use_case(ctx: TenantContext) -> DeleteLeadUseCase:
    return DeleteLeadUseCase(DjangoLeadRepository(company_id=ctx.company_id), DjangoTaskRepository(company_id=ctx.company_id), DjangoCallRepository(company_id=ctx.company_id), DjangoTimelineRepository(company_id=ctx.company_id), DjangoTransactionManager())


def get_convert_lead_use_case(ctx: TenantContext) -> ConvertLeadUseCase:
    return ConvertLeadUseCase(DjangoLeadRepository(company_id=ctx.company_id), DjangoAccountRepository(company_id=ctx.company_id), DjangoContactRepository(company_id=ctx.company_id), DjangoUserRepository(company_id=ctx.company_id), DjangoTransactionManager(), recorder(ctx))


def get_conversion_check_use_case(ctx: TenantContext) -> ConversionCheckUseCase:
    return ConversionCheckUseCase(DjangoLeadRepository(company_id=ctx.company_id), DjangoAccountRepository(company_id=ctx.company_id), DjangoContactRepository(company_id=ctx.company_id))
