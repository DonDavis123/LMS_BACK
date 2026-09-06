from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.use_cases.update_lead import (
    _UNSET,
)
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_update_lead_use_case,
)

from ..serializers import UpdateLeadSerializer


class UpdateLeadView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def patch(self, request, lead_id):

        serializer = UpdateLeadSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = serializer.validated_data

        lead_source = data.get("lead_source")

        if lead_source is not None:
            lead_source = LeadSource(lead_source)

        email = (
            data["email"]
            if "email" in data
            else _UNSET
        )

        use_case = get_update_lead_use_case()

        try:
            lead = use_case.execute(
                lead_id=UUID(str(lead_id)),
                name=data.get("name"),
                company_name=data.get("company_name"),
                email=email,
                mobile_number=data.get("mobile_number"),
                lead_source=lead_source,
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(lead.id),
                "name": lead.name,
                "company_name": lead.company_name,
                "email": lead.email,
                "mobile_number": lead.mobile_number,
                "lead_source": lead.lead_source.value,
                "owner_id": str(lead.owner_id),
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
            },
            status=status.HTTP_200_OK,
        )