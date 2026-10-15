from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin

from ..dependencies.company_dependencies import (
    get_activate_company_use_case,
    get_suspend_company_use_case,
)
from ..serializers.company import CompanySerializer, SuspendCompanySerializer
from ._common import error_response, load_actor


class SuspendCompanyView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, company_id: UUID):
        serializer = SuspendCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            company = get_suspend_company_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                reason=serializer.validated_data["reason"],
            )
        except ValueError as error:
            return error_response(error)

        return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)


class ActivateCompanyView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, company_id: UUID):
        try:
            company = get_activate_company_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
            )
        except ValueError as error:
            return error_response(error)

        return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)
