from src.modules.calendar.application.use_cases.get_calendar_events import (
    GetCalendarEventsUseCase,
)
from src.modules.calendar.infrastructure.persistence.django_calendar_repository import (
    DjangoCalendarRepository,
)
from src.modules.shared.application.tenant_context import TenantContext


def get_calendar_events_use_case(ctx: TenantContext) -> GetCalendarEventsUseCase:
    return GetCalendarEventsUseCase(
        DjangoCalendarRepository(company_id=ctx.company_id),
    )
