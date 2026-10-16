from src.modules.dashboard.application.use_cases.get_dashboard_stats import (
    GetDashboardStatsUseCase,
)
from src.modules.dashboard.infrastructure.persistence.django_dashboard_repository import (
    DjangoDashboardRepository,
)
from src.modules.shared.application.tenant_context import TenantContext


def get_dashboard_stats_use_case(ctx: TenantContext) -> GetDashboardStatsUseCase:
    return GetDashboardStatsUseCase(DjangoDashboardRepository(company_id=ctx.company_id))
