from src.modules.leads.application.use_cases.create_lead import (
    CreateLeadUseCase,
)
from src.modules.leads.application.use_cases.update_lead import (
    UpdateLeadUseCase,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)

from src.modules.leads.application.use_cases.get_leads import (
    GetLeadsUseCase,
)


def get_create_lead_use_case() -> CreateLeadUseCase:
    lead_repository = DjangoLeadRepository()

    return CreateLeadUseCase(
        lead_repository=lead_repository,
    )


def get_update_lead_use_case() -> UpdateLeadUseCase:
    lead_repository = DjangoLeadRepository()

    return UpdateLeadUseCase(
        lead_repository=lead_repository,
    )


def get_leads_use_case() -> GetLeadsUseCase:
    lead_repository = DjangoLeadRepository()

    return GetLeadsUseCase(
        lead_repository=lead_repository,
    )