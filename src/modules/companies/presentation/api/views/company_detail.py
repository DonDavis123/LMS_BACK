from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.companies.application.use_cases.update_company import (
    UpdateCompanyUseCase,
)
from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin

from ..dependencies.company_dependencies import (
    get_company_details_use_case,
    get_update_company_use_case,
)
from ..serializers.company import (
    CompanyDetailSerializer,
    CompanySerializer,
    UpdateCompanySerializer,
)
from ._common import error_response, load_actor


class CompanyDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request, company_id: UUID):
        try:
            detail = get_company_details_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            CompanyDetailSerializer(detail).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, company_id: UUID):
        serializer = UpdateCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            company = get_update_company_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                name=data.get("name", UpdateCompanyUseCase.UNSET),
                website=data.get("website", UpdateCompanyUseCase.UNSET),
            )
        except ValueError as error:
            return error_response(error)

        return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)
