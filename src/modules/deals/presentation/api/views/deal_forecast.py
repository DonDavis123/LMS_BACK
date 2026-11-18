from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.deals.application.dto.deal_forecast import DealForecastQuery
from src.modules.deals.presentation.api.dependencies.deal_dependencies import (
    get_deal_forecast_use_case,
)
from src.modules.deals.presentation.api.errors import validation_error_response
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.deal_forecast import (
    DealForecastQuerySerializer,
    DealForecastSerializer,
)


class DealForecastView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        params = DealForecastQuerySerializer(data=request.query_params)
        if not params.is_valid():
            return validation_error_response(params)

        data = params.validated_data

        query = DealForecastQuery(
            timezone_name=data["tz"],
            owner_id=data.get("owner_id"),
        )

        try:
            forecast = get_deal_forecast_use_case(
                get_tenant_context(request)
            ).execute(query)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DealForecastSerializer(forecast).data,
            status=status.HTTP_200_OK,
        )
