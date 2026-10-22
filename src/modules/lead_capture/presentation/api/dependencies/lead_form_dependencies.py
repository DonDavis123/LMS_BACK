from uuid import UUID

from src.modules.lead_capture.application.interfaces.public_lead_form_lookup import (
    PublicFormTarget,
)
from src.modules.lead_capture.application.use_cases.change_lead_form_state import (
    BlockLeadFormUseCase,
    RegenerateLeadFormLinkUseCase,
    UnblockLeadFormUseCase,
)
from src.modules.lead_capture.application.use_cases.get_lead_form import (
    GetLeadFormUseCase,
)
from src.modules.lead_capture.application.use_cases.get_public_lead_form import (
    GetPublicLeadFormUseCase,
)
from src.modules.lead_capture.application.use_cases.submit_public_lead import (
    SubmitPublicLeadUseCase,
)
from src.modules.lead_capture.application.use_cases.update_lead_form import (
    UpdateLeadFormUseCase,
)
from src.modules.lead_capture.infrastructure.persistence.django_public_lead_form_lookup import (
    DjangoPublicLeadFormLookup,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_create_lead_use_case,
    get_update_lead_use_case,
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


# ------------------------------------------------------------------- public


def resolve_public_form(public_token: str) -> PublicFormTarget | None:
    """Token -> company. The only non-tenant lookup (see the lookup class)."""
    return DjangoPublicLeadFormLookup().find_by_token(public_token)


def get_public_lead_form_use_case(company_id: UUID) -> GetPublicLeadFormUseCase:
    return GetPublicLeadFormUseCase(
        DjangoLeadFormRepository(company_id=company_id),
        DjangoUserRepository(company_id=company_id),
    )


def get_submit_public_lead_use_case(company_id: UUID) -> SubmitPublicLeadUseCase:
    return SubmitPublicLeadUseCase(
        DjangoLeadFormRepository(company_id=company_id),
        DjangoUserRepository(company_id=company_id),
        DjangoLeadRepository(company_id=company_id),
        get_create_lead_use_case,
        get_update_lead_use_case,
        DjangoTransactionManager(),
    )
