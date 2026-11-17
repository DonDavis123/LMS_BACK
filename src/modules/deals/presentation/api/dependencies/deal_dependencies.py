from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.deals.application.use_cases.create_deal import CreateDealUseCase
from src.modules.deals.application.use_cases.delete_deal import DeleteDealUseCase
from src.modules.deals.application.use_cases.get_deal import GetDealUseCase
from src.modules.deals.application.use_cases.get_deals import GetDealsUseCase
from src.modules.deals.application.use_cases.move_deal_stage import MoveDealStageUseCase
from src.modules.deals.application.use_cases.update_deal import UpdateDealUseCase
from src.modules.deals.infrastructure.persistence.django_deal_repository import DjangoDealRepository
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def transaction_manager():
    return DjangoTransactionManager()


def get_create_deal_use_case(ctx: TenantContext) -> CreateDealUseCase:
    return CreateDealUseCase(
        DjangoDealRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoLeadRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )


def get_deal_use_case(ctx: TenantContext) -> GetDealUseCase:
    return GetDealUseCase(DjangoDealRepository(company_id=ctx.company_id))


def get_deals_use_case(ctx: TenantContext) -> GetDealsUseCase:
    return GetDealsUseCase(DjangoDealRepository(company_id=ctx.company_id))


def get_update_deal_use_case(ctx: TenantContext) -> UpdateDealUseCase:
    return UpdateDealUseCase(
        DjangoDealRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )


def get_delete_deal_use_case(ctx: TenantContext) -> DeleteDealUseCase:
    return DeleteDealUseCase(
        DjangoDealRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )


def get_move_deal_stage_use_case(ctx: TenantContext) -> MoveDealStageUseCase:
    return MoveDealStageUseCase(
        DjangoDealRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
    )
