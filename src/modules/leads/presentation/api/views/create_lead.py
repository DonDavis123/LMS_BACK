from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_create_lead_use_case,
)

from ..serializers import CreateLeadSerializer


class CreateLeadView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

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
            company_name=data["company_name"],
            email=data.get("email"),
            mobile_number=data["mobile_number"],
            lead_source=LeadSource(
                data["lead_source"]
            ),
            owner_id=request.user.id,
        )

        use_case = get_create_lead_use_case()

        lead = use_case.execute(dto)

        return Response(
            {
                "id": str(lead.id),
                "message": "Lead created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )