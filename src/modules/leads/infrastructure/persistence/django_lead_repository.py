from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.business_type import BusinessType
from src.modules.leads.domain.entities.lead import Lead

from .django_lead_model import DjangoLeadModel


class DjangoLeadRepository(LeadRepository):

    def save(self, lead: Lead) -> Lead:

        model = DjangoLeadModel.objects.create(
            id=lead.id,
            lead_generator=lead.lead_generator,
            client_partner_name=lead.client_partner_name,
            mobile_number=lead.mobile_number,
            email=lead.email,
            city_location=lead.city_location,
            business_type=lead.business_type.value,
            lead_source=lead.lead_source,
            remarks=lead.remarks,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )

        return self._to_domain(model)

    def get_by_id(self, lead_id: UUID) -> Lead | None:

        try:
            model = DjangoLeadModel.objects.get(id=lead_id)
        except DjangoLeadModel.DoesNotExist:
            return None

        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: DjangoLeadModel) -> Lead:

        return Lead(
            id=model.id,
            lead_generator=model.lead_generator,
            client_partner_name=model.client_partner_name,
            mobile_number=model.mobile_number,
            email=model.email,
            city_location=model.city_location,
            business_type=BusinessType(model.business_type),
            remarks=model.remarks,
            lead_source=model.lead_source,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    def get_all(self) -> list[Lead]:
       models = DjangoLeadModel.objects.all()

       return [
          self._to_domain(model)
          for model in models
        ]