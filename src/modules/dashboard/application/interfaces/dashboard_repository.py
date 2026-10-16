from abc import ABC, abstractmethod

from src.modules.dashboard.application.dto.dashboard_stats import (
    DashboardWindow,
    LeadStatsDTO,
)


class DashboardRepository(ABC):

    @abstractmethod
    def get_lead_stats(self, window: DashboardWindow) -> LeadStatsDTO:
        """Aggregate the company's lead numbers for ``window`` in the database."""
        pass
