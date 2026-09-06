from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_source import LeadSource

from .django_lead_model import DjangoLeadModel


class DjangoLeadRepository(LeadRepository):

    def save(self, lead: Lead) -> Lead:
        model, created = DjangoLeadModel.objects.update_or_create(
            id=lead.id,
            defaults={
                "name": lead.name,
                "company_name": lead.company_name,
                "email": lead.email,
                "mobile_number": lead.mobile_number,
                "lead_source": lead.lead_source.value,
                "owner_id": lead.owner_id,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, lead_id: UUID) -> Lead | None:
        try:
            model = DjangoLeadModel.objects.get(id=lead_id)
        except DjangoLeadModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self) -> list[Lead]:
        models = DjangoLeadModel.objects.all()

        return [
            self._to_domain(model)
            for model in models
        ]

    def get_all_with_owner(self) -> list[tuple[Lead, str]]:
        models = DjangoLeadModel.objects.select_related("owner").all()

        return [
            (
                self._to_domain(model),
                model.owner.name,
            )
            for model in models
        ]

    @staticmethod
    def _to_domain(model: DjangoLeadModel) -> Lead:
        return Lead(
            id=model.id,
            name=model.name,
            company_name=model.company_name,
            email=model.email,
            mobile_number=model.mobile_number,
            lead_source=LeadSource(model.lead_source),
            owner_id=model.owner_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )