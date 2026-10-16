from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.dashboard.presentation.api.dependencies.dashboard_dependencies import (
    get_dashboard_stats_use_case,
)
from src.modules.dashboard.presentation.api.serializers import (
    DashboardStatsQuerySerializer,
    DashboardStatsSerializer,
)
from src.modules.dashboard.presentation.permissions.can_view_dashboard import (
    CanViewDashboard,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class DashboardStatsView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsCompanyUser,
        CanViewDashboard,
    ]

    def get(self, request):
        query = DashboardStatsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        try:
            stats = get_dashboard_stats_use_case(get_tenant_context(request)).execute(
                query.validated_data["range"],
                query.validated_data["tz"],
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DashboardStatsSerializer(stats).data,
            status=status.HTTP_200_OK,
        )
