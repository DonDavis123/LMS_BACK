from uuid import UUID

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from zoneinfo import ZoneInfo

from src.modules.dashboard.application.dto.dashboard_stats import (
    DashboardWindow,
    LeadCountsDTO,
    LeadStatsDTO,
)
from src.modules.dashboard.application.interfaces.dashboard_repository import (
    DashboardRepository,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)


class DjangoDashboardRepository(DashboardRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def get_lead_stats(self, window: DashboardWindow) -> LeadStatsDTO:
        # Same population as the leads list: not deleted, not converted.
        company_leads = DjangoLeadModel.objects.filter(
            company_id=self._company_id,
            is_deleted=False,
        )
        open_leads = company_leads.filter(is_converted=False)
        in_range = Q(created_at__gte=window.from_at, created_at__lt=window.to_at)
        previous = Q(created_at__gte=window.previous_from_at, created_at__lt=window.from_at)

        # 1 query: every headline number.
        counts = company_leads.aggregate(
            total=Count("id", filter=Q(is_converted=False)),
            new_in_range=Count("id", filter=Q(is_converted=False) & in_range),
            new_previous_range=Count("id", filter=Q(is_converted=False) & previous),
            converted=Count("id", filter=Q(is_converted=True)),
        )

        # 1 query: pipeline (all open leads).
        by_status = [
            (row["lead_status"], row["count"])
            for row in open_leads.values("lead_status").annotate(count=Count("id"))
        ]

        range_leads = open_leads.filter(in_range)

        # 1 query: lead sources for the selected range.
        by_source = [
            (row["lead_source"], row["count"])
            for row in range_leads.values("lead_source").annotate(count=Count("id"))
        ]

        # 1 query: per-day counts, bucketed by calendar day in the caller's time zone.
        per_day = {
            row["day"]: row["count"]
            for row in range_leads.annotate(
                day=TruncDate("created_at", tzinfo=ZoneInfo(window.timezone_name))
            )
            .values("day")
            .annotate(count=Count("id"))
        }

        return LeadStatsDTO(
            counts=LeadCountsDTO(
                total=counts["total"],
                new_in_range=counts["new_in_range"],
                new_previous_range=counts["new_previous_range"],
                converted=counts["converted"],
            ),
            by_status=by_status,
            by_source=by_source,
            created_per_day=per_day,
        )
