from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):

        use_case = get_lead_details_use_case()

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
            lead_source=lead.lead_source.value,
            lead_status=lead.lead_status.value,
            industry=lead.industry.value,
            rating=lead.rating.value,
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
        )

        serializer = LeadDetailSerializer(dto)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )