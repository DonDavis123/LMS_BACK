from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.deals.application.dto.move_deal_stage import MoveDealStageDTO
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.deals.presentation.api.dependencies.deal_dependencies import (
    get_move_deal_stage_use_case,
)
from src.modules.deals.presentation.api.errors import validation_error_response
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.deal import DealSerializer
from ..serializers.move_deal_stage import MoveDealStageSerializer


class DealMoveStageView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request, deal_id):
        serializer = MoveDealStageSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer)

        data = serializer.validated_data

        dto = MoveDealStageDTO(
            deal_id=deal_id,
            stage=DealStage(data["stage"]),
            probability=data.get("probability"),
            lost_reason=data.get("lost_reason"),
        )

        try:
            deal = get_move_deal_stage_use_case(get_tenant_context(request)).execute(
                dto, current_user_id=request.user.id
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DealSerializer(deal).data,
            status=status.HTTP_200_OK,
        )
