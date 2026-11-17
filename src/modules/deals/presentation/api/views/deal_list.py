from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.deals.application.dto.create_deal import CreateDealDTO
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.deals.presentation.api.dependencies.deal_dependencies import (
    get_create_deal_use_case,
    get_deals_use_case,
)
from src.modules.deals.presentation.api.errors import validation_error_response
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.create_deal import CreateDealSerializer
from ..serializers.deal import DealSerializer
from ..serializers.deal_read import DealReadSerializer


class DealListView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            result = get_deals_use_case(get_tenant_context(request)).execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealReadSerializer(result.results, many=True)

        return Response(
            {
                "results": serializer.data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateDealSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer)

        data = serializer.validated_data

        dto = CreateDealDTO(
            name=data["name"],
            owner_id=data["owner_id"],
            created_by_id=request.user.id,
            amount=data["amount"],
            expected_close_date=data.get("expected_close_date"),
            stage=DealStage(data["stage"]),
            probability=data.get("probability"),
            account_id=data.get("account_id"),
            contact_id=data.get("contact_id"),
            source_lead_id=data.get("source_lead_id"),
            lead_source=data.get("lead_source"),
            description=data.get("description"),
            lost_reason=data.get("lost_reason"),
        )

        try:
            deal = get_create_deal_use_case(get_tenant_context(request)).execute(dto)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DealSerializer(deal).data,
            status=status.HTTP_201_CREATED,
        )
