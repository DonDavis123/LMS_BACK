from src.modules.shared.application.tenant_context import TenantContext
from src.modules.timeline.application.use_cases.get_timeline import GetTimelineUseCase
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository


def get_timeline_use_case(ctx: TenantContext) -> GetTimelineUseCase:
    return GetTimelineUseCase(
        timeline_repository=DjangoTimelineRepository(company_id=ctx.company_id),
    )
