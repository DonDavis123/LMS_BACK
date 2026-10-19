from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from src.modules.shared.presentation.permissions import IsCompanyUser
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.leads.domain.entities.option_text import option_text
from src.modules.leads.application.dto.lead_detail import (
    LeadDetailResponseDTO,
)
from src.modules.leads.application.dto.owner_response import (
    OwnerResponseDTO,
)
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_lead_details_use_case,
)

from ..serializers.lead_details import LeadDetailSerializer


class GetLeadDetailsView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, lead_id):

        use_case = get_lead_details_use_case(get_tenant_context(request))

        try:
            lead, owner_name = use_case.execute(
                UUID(str(lead_id))
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        dto = LeadDetailResponseDTO(
            id=lead.id,
            name=lead.name,
            title=lead.title,
            company_name=lead.company_name,
            email=lead.email,
            mobile_number=lead.mobile_number,
            phone=lead.phone,
            lead_source=option_text(lead.lead_source),
            lead_status=option_text(lead.lead_status),
            industry=option_text(lead.industry),
            rating=option_text(lead.rating),
            website=lead.website,
            number_of_employees=lead.number_of_employees,
            annual_revenue=lead.annual_revenue,
            owner=OwnerResponseDTO(
                id=lead.owner_id,
                name=owner_name,
            ),
            address=lead.address,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            postal_code=lead.postal_code,
            description=lead.description,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            is_converted=lead.is_converted,
        )

        serializer = LeadDetailSerializer(dto)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )