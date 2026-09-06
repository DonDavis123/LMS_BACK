from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.leads.domain.entities.lead import Lead


class LeadRepository(ABC):

    @abstractmethod
    def save(self, lead: Lead) -> Lead:
        pass

    @abstractmethod
    def get_by_id(self, lead_id: UUID) -> Lead | None:
        pass

    @abstractmethod
    def get_all(self) -> list[Lead]:
        pass

    @abstractmethod
    def get_all_with_owner(self) -> list[tuple[Lead, str]]:
        pass