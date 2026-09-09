from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus

from .django_lead_model import DjangoLeadModel


class DjangoLeadRepository(LeadRepository):

    def save(self, lead: Lead) -> Lead:
        model, created = DjangoLeadModel.objects.update_or_create(
            id=lead.id,
            defaults={
                # Basic information
                "name": lead.name,
                "title": lead.title,
                "company_name": lead.company_name,
                "email": lead.email,
                "mobile_number": lead.mobile_number,
                "phone": lead.phone,

                # Lead information
                "lead_source": lead.lead_source.value,
                "lead_status": lead.lead_status.value,
                "industry": lead.industry.value,
                "rating": lead.rating.value,

                # Business information
                "website": lead.website,
                "number_of_employees": lead.number_of_employees,
                "annual_revenue": lead.annual_revenue,

                # Ownership
                "owner_id": lead.owner_id,

                # Address
                "address": lead.address,
                "city": lead.city,
                "state": lead.state,
                "country": lead.country,
                "postal_code": lead.postal_code,

                # Additional information
                "description": lead.description,

                # Backend controlled lifecycle
                "is_deleted": lead.is_deleted,
                "is_converted": lead.is_converted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, lead_id: UUID) -> Lead | None:
        try:
            model = DjangoLeadModel.objects.get(
                id=lead_id
            )
        except DjangoLeadModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_by_id_with_owner(
        self,
        lead_id: UUID,
    ) -> tuple[Lead, str] | None:
        try:
            model = (
                DjangoLeadModel.objects
                .select_related("owner")
                .get(id=lead_id)
            )
        except DjangoLeadModel.DoesNotExist:
            return None

        return (
            self._to_domain(model),
            model.owner.name,
        )

    def get_all(self) -> list[Lead]:
        models = DjangoLeadModel.objects.filter(
            is_deleted=False,
            is_converted=False,
        )

        return [
            self._to_domain(model)
            for model in models
        ]

    def get_all_with_owner(
        self,
    ) -> list[tuple[Lead, str]]:
        models = (
            DjangoLeadModel.objects
            .select_related("owner")
            .filter(
                is_deleted=False,
                is_converted=False,
            )
        )

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
            # Basic information
            id=model.id,
            name=model.name,
            title=model.title,
            company_name=model.company_name,
            email=model.email,
            mobile_number=model.mobile_number,
            phone=model.phone,

            # Lead information
            lead_source=LeadSource(model.lead_source),
            lead_status=LeadStatus(model.lead_status),
            industry=LeadIndustry(model.industry),
            rating=LeadRating(model.rating),

            # Business information
            website=model.website,
            number_of_employees=model.number_of_employees,
            annual_revenue=model.annual_revenue,

            # Ownership
            owner_id=model.owner_id,

            # Address
            address=model.address,
            city=model.city,
            state=model.state,
            country=model.country,
            postal_code=model.postal_code,

            # Additional information
            description=model.description,

            # Backend controlled lifecycle
            is_deleted=model.is_deleted,
            is_converted=model.is_converted,

            # Backend controlled timestamps
            created_at=model.created_at,
            updated_at=model.updated_at,
        )