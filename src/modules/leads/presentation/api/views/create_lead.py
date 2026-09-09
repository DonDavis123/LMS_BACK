from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_create_lead_use_case,
)

from ..serializers.createLead import CreateLeadSerializer


class CreateLeadView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateLeadSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        dto = CreateLeadDTO(
            name=data["name"],
            title=data.get("title"),

            company_name=data["company_name"],
            email=data.get("email"),
            mobile_number=data.get("mobile_number"),
            phone=data.get("phone"),

            lead_source=(
                LeadSource(data["lead_source"])
                if data.get("lead_source")
                else None
            ),

            lead_status=(
                LeadStatus(data["lead_status"])
                if data.get("lead_status")
                else None
            ),

            industry=(
                LeadIndustry(data["industry"])
                if data.get("industry")
                else None
            ),

            rating=(
                LeadRating(data["rating"])
                if data.get("rating")
                else None
            ),

            website=data.get("website"),
            number_of_employees=data.get(
                "number_of_employees"
            ),
            annual_revenue=data.get(
                "annual_revenue"
            ),

            owner_id=data.get("owner_id"),

            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            country=data.get("country"),
            postal_code=data.get("postal_code"),

            description=data.get("description"),
        )

        use_case = get_create_lead_use_case()

        try:
            lead = use_case.execute(
                dto,
                request.user.id,
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(lead.id),
                "message": "Lead created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )