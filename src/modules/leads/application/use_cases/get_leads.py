from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.lead import Lead


class GetLeadsUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self) -> list[Lead]:
        return self.lead_repository.get_all()