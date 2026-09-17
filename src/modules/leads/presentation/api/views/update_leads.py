from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.dto.update_lead import (
    UpdateLeadDTO,
)
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_update_lead_use_case,
)

from ..serializers.update_lead import UpdateLeadSerializer


class UpdateLeadView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, lead_id):

        serializer = UpdateLeadSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        dto_data = {
            "lead_id": UUID(str(lead_id)),
        }

        if "name" in data:
            dto_data["name"] = data["name"]

        if "title" in data:
            dto_data["title"] = data["title"]

        if "company_name" in data:
            dto_data["company_name"] = data["company_name"]

        if "email" in data:
            dto_data["email"] = data["email"]

        if "mobile_number" in data:
            dto_data["mobile_number"] = data["mobile_number"]

        if "phone" in data:
            dto_data["phone"] = data["phone"]

        if "lead_source" in data:
            dto_data["lead_source"] = LeadSource(
                data["lead_source"]
            )

        if "lead_status" in data:
            dto_data["lead_status"] = LeadStatus(
                data["lead_status"]
            )

        if "industry" in data:
            dto_data["industry"] = LeadIndustry(
                data["industry"]
            )

        if "rating" in data:
            dto_data["rating"] = LeadRating(
                data["rating"]
            )

        if "website" in data:
            dto_data["website"] = data["website"]

        if "number_of_employees" in data:
            dto_data["number_of_employees"] = data[
                "number_of_employees"
            ]

        if "annual_revenue" in data:
            dto_data["annual_revenue"] = data[
                "annual_revenue"
            ]

        # Owner
        if "owner_id" in data:
            dto_data["owner_id"] = data["owner_id"]

        if "address" in data:
            dto_data["address"] = data["address"]

        if "city" in data:
            dto_data["city"] = data["city"]

        if "state" in data:
            dto_data["state"] = data["state"]

        if "country" in data:
            dto_data["country"] = data["country"]

        if "postal_code" in data:
            dto_data["postal_code"] = data["postal_code"]

        if "description" in data:
            dto_data["description"] = data["description"]

        dto = UpdateLeadDTO(**dto_data)

        use_case = get_update_lead_use_case()

        try:
            lead = use_case.execute(dto, current_user_id=request.user.id)

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(lead.id),
                "message": "Lead updated successfully.",
            },
            status=status.HTTP_200_OK,
        )