from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.companies.application.dto.company_dto import CreateCompanyDTO
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery
from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.users.presentation.api.serializers.user import UserSerializer

from ..dependencies.company_dependencies import (
    get_companies_use_case,
    get_create_company_use_case,
)
from ..serializers.company import (
    CompanyListSerializer,
    CompanySerializer,
    CreateCompanySerializer,
)
from ._common import error_response, load_actor


class CompanyListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request):
        try:
            current_user = load_actor(request)
            query = parse_list_query(request.query_params)

            # Convenience: ?status=ACTIVE is the same as the JSON filter.
            status_param = request.query_params.get("status")
            if status_param:
                query = ListQuery(
                    filters=query.filters
                    + (FilterCondition("status", "equals", status_param.strip().upper()),),
                    page=query.page,
                    page_size=query.page_size,
                    sort_by=query.sort_by,
                    sort_direction=query.sort_direction,
                    search=query.search,
                )

            result = get_companies_use_case().execute(
                current_user=current_user,
                query=query,
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {
                "results": CompanyListSerializer(result.results, many=True).data,
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
        serializer = CreateCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            current_user = load_actor(request)
            company, admin = get_create_company_use_case().execute(
                current_user=current_user,
                data=CreateCompanyDTO(
                    company_name=data["company_name"],
                    website=data.get("website"),
                    admin_name=data["admin_name"],
                    admin_email=data["admin_email"],
                    admin_password=data["admin_password"],
                ),
            )
        except ValueError as error:
            return error_response(error)
        except IntegrityError:
            return Response(
                {"detail": "User with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "company": CompanySerializer(company).data,
                "admin": UserSerializer(admin).data,
            },
            status=status.HTTP_201_CREATED,
        )
