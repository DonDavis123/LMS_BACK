from src.modules.lead_capture.application.use_cases.change_lead_form_state import (
    BlockLeadFormUseCase,
    RegenerateLeadFormLinkUseCase,
    UnblockLeadFormUseCase,
)
from src.modules.lead_capture.application.use_cases.get_lead_form import (
    GetLeadFormUseCase,
)
from src.modules.lead_capture.application.use_cases.update_lead_form import (
    UpdateLeadFormUseCase,
)
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_repository import (
    DjangoLeadFormRepository,
)
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import (
    DjangoPicklistRepository,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def get_lead_form_use_case(ctx: TenantContext) -> GetLeadFormUseCase:
    return GetLeadFormUseCase(
        DjangoLeadFormRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
    )


def get_update_lead_form_use_case(ctx: TenantContext) -> UpdateLeadFormUseCase:
    return UpdateLeadFormUseCase(
        DjangoLeadFormRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoPicklistRepository(company_id=ctx.company_id),
        DjangoTransactionManager(),
    )


def _state_args(ctx: TenantContext):
    return (
        DjangoLeadFormRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoTransactionManager(),
    )


def get_block_lead_form_use_case(ctx: TenantContext) -> BlockLeadFormUseCase:
    return BlockLeadFormUseCase(*_state_args(ctx))


def get_unblock_lead_form_use_case(ctx: TenantContext) -> UnblockLeadFormUseCase:
    return UnblockLeadFormUseCase(*_state_args(ctx))


def get_regenerate_lead_form_link_use_case(
    ctx: TenantContext,
) -> RegenerateLeadFormLinkUseCase:
    return RegenerateLeadFormLinkUseCase(*_state_args(ctx))
