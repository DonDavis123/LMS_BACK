from django.conf import settings

from src.modules.dashboard.application.use_cases.generate_daily_briefing import (
    GenerateDailyBriefingUseCase,
)
from src.modules.dashboard.application.use_cases.get_dashboard_stats import (
    GetDashboardStatsUseCase,
)
from src.modules.dashboard.infrastructure.briefing.gemini_daily_briefing_generator import (
    GeminiBriefingConfig,
    GeminiDailyBriefingGenerator,
)
from src.modules.dashboard.infrastructure.persistence.django_dashboard_repository import (
    DjangoDashboardRepository,
)
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)


def get_dashboard_stats_use_case(ctx: TenantContext) -> GetDashboardStatsUseCase:
    return GetDashboardStatsUseCase(DjangoDashboardRepository(company_id=ctx.company_id))


def get_daily_briefing_generator() -> GeminiDailyBriefingGenerator:
    return GeminiDailyBriefingGenerator(
        GeminiBriefingConfig(
            api_key=getattr(settings, "GEMINI_API_KEY", ""),
            model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
            timeout_seconds=int(getattr(settings, "DAILY_BRIEFING_TIMEOUT_SECONDS", 60)),
            briefing_language=getattr(
                settings,
                "DAILY_BRIEFING_LANGUAGE",
                getattr(settings, "CALL_TRANSCRIPTION_SUMMARY_LANGUAGE", "English"),
            ),
        )
    )


def get_daily_briefing_use_case(ctx: TenantContext) -> GenerateDailyBriefingUseCase:
    return GenerateDailyBriefingUseCase(
        DjangoTaskRepository(company_id=ctx.company_id),
        DjangoMeetingRepository(company_id=ctx.company_id),
        get_daily_briefing_generator(),
    )
