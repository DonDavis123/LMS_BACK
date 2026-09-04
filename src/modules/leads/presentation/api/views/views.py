from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.use_cases.create_lead import CreateLeadUseCase
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)

from ..serializers.serializers import CreateLeadSerializer
from src.modules.leads.domain.entities.business_type import BusinessType


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
            lead_generator=request.user.name,
            client_partner_name=data["client_partner_name"],
            mobile_number=data["mobile_number"],
            email=data.get("email"),
            city_location=data.get("city_location"),
            business_type=BusinessType(
                data["business_type"]
            ),
            lead_source=data["lead_source"],
            remarks=data.get("remarks"),
        )

        use_case = CreateLeadUseCase(
            lead_repository=DjangoLeadRepository(),
        )

        lead = use_case.execute(dto)

        return Response(
            {
                "id": str(lead.id),
                "message": "Lead created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )