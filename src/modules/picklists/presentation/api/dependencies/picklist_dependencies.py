from src.modules.picklists.application.use_cases.create_option import (
    CreatePicklistOptionUseCase,
)
from src.modules.picklists.application.use_cases.delete_option import (
    DeletePicklistOptionUseCase,
)
from src.modules.picklists.application.use_cases.get_picklists import (
    GetPicklistsUseCase,
)
from src.modules.picklists.application.use_cases.reorder_options import (
    ReorderPicklistOptionsUseCase,
)
from src.modules.picklists.application.use_cases.update_option import (
    UpdatePicklistOptionUseCase,
)
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import (
    DjangoPicklistRepository,
)
from src.modules.picklists.infrastructure.persistence.django_picklist_usage_gateway import (
    DjangoPicklistUsageGateway,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)


def get_picklists_use_case(ctx: TenantContext) -> GetPicklistsUseCase:
    return GetPicklistsUseCase(
        DjangoPicklistRepository(company_id=ctx.company_id),
        DjangoPicklistUsageGateway(company_id=ctx.company_id),
    )


def get_create_option_use_case(ctx: TenantContext) -> CreatePicklistOptionUseCase:
    return CreatePicklistOptionUseCase(
        DjangoPicklistRepository(company_id=ctx.company_id),
    )


def get_update_option_use_case(ctx: TenantContext) -> UpdatePicklistOptionUseCase:
    return UpdatePicklistOptionUseCase(
        DjangoPicklistRepository(company_id=ctx.company_id),
        DjangoPicklistUsageGateway(company_id=ctx.company_id),
        DjangoTransactionManager(),
    )


def get_delete_option_use_case(ctx: TenantContext) -> DeletePicklistOptionUseCase:
    return DeletePicklistOptionUseCase(
        DjangoPicklistRepository(company_id=ctx.company_id),
        DjangoPicklistUsageGateway(company_id=ctx.company_id),
        DjangoTransactionManager(),
    )


def get_reorder_options_use_case(ctx: TenantContext) -> ReorderPicklistOptionsUseCase:
    return ReorderPicklistOptionsUseCase(
        DjangoPicklistRepository(company_id=ctx.company_id),
    )
