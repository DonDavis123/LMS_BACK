from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.deals.application.dto.update_deal import UpdateDealDTO
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.deals.presentation.api.dependencies.deal_dependencies import (
    get_deal_use_case,
    get_delete_deal_use_case,
    get_update_deal_use_case,
)
from src.modules.deals.presentation.api.errors import validation_error_response
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.deal import DealSerializer
from ..serializers.deal_read import DealReadSerializer
from ..serializers.update_deal import UpdateDealSerializer


class DealDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, deal_id):
        deal = get_deal_use_case(get_tenant_context(request)).execute(deal_id)

        if deal is None:
            return Response(
                {"detail": "Deal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            DealReadSerializer(deal).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, deal_id):
        serializer = UpdateDealSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer)

        fields = dict(serializer.validated_data)

        if "stage" in fields:
            fields["stage"] = DealStage(fields["stage"])

        dto = UpdateDealDTO(deal_id=deal_id, fields=fields)

        try:
            deal = get_update_deal_use_case(get_tenant_context(request)).execute(
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

    def delete(self, request, deal_id):
        try:
            get_delete_deal_use_case(get_tenant_context(request)).execute(
                deal_id, current_user_id=request.user.id
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Deal deleted successfully."},
            status=status.HTTP_200_OK,
        )
