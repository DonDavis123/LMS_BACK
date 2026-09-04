from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.use_cases.update_lead import (
    UpdateLeadUseCase,
)

from src.modules.leads.domain.entities.business_type import BusinessType

from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)

from ..serializers import (
    UpdateLeadSerializer,
)


class UpdateLeadView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def patch(self, request, lead_id):

        serializer = UpdateLeadSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = serializer.validated_data

        use_case = UpdateLeadUseCase(
            lead_repository=DjangoLeadRepository(),
        )

        try:
            business_type = data.get("business_type")

            if business_type is not None:
                business_type = BusinessType(
                    business_type
                )

            lead = use_case.execute(
                lead_id=UUID(str(lead_id)),
                client_partner_name=data.get(
                    "client_partner_name"
                ),
                mobile_number=data.get(
                    "mobile_number"
                ),
                email=data.get(
                    "email"
                ),
                city_location=data.get(
                    "city_location"
                ),
                business_type=business_type,
                lead_source=data.get(
                    "lead_source"
                ),
                remarks=data.get(
                    "remarks"
                ),
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(lead.id),
                "lead_generator": lead.lead_generator,
                "client_partner_name": lead.client_partner_name,
                "mobile_number": lead.mobile_number,
                "email": lead.email,
                "city_location": lead.city_location,
                "business_type": lead.business_type.value,
                "lead_source": lead.lead_source,
                "remarks": lead.remarks,
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
            },
            status=status.HTTP_200_OK,
        )