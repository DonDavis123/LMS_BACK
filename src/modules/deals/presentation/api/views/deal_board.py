from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.deals.application.dto.deal_board import DealBoardQuery
from src.modules.deals.presentation.api.dependencies.deal_dependencies import (
    get_deal_board_use_case,
)
from src.modules.deals.presentation.api.errors import validation_error_response
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.deal_board import DealBoardQuerySerializer, DealBoardSerializer


class DealBoardView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        params = DealBoardQuerySerializer(data=request.query_params)
        if not params.is_valid():
            return validation_error_response(params)

        data = params.validated_data

        query = DealBoardQuery(
            owner_id=data.get("owner_id"),
            expected_close_from=data.get("expected_close_from"),
            expected_close_to=data.get("expected_close_to"),
            search=data.get("search"),
            closed_within_days=data["closed_within_days"],
        )

        try:
            columns = get_deal_board_use_case(get_tenant_context(request)).execute(query)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DealBoardSerializer({"stages": columns}).data,
            status=status.HTTP_200_OK,
        )
