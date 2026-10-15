from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin

from ..dependencies.company_dependencies import get_platform_overview_use_case
from ..serializers.company import RecentCompanySerializer
from ._common import error_response, load_actor


class PlatformOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request):
        try:
            overview = get_platform_overview_use_case().execute(
                current_user=load_actor(request),
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {
                "companies": {
                    "total": overview.companies_total,
                    "active": overview.companies_active,
                    "onboarding": overview.companies_onboarding,
                    "suspended": overview.companies_suspended,
                },
                "users": {
                    "total": overview.users_total,
                    "active": overview.users_active,
                },
                "recent_companies": RecentCompanySerializer(
                    overview.recent_companies, many=True
                ).data,
            },
            status=status.HTTP_200_OK,
        )
