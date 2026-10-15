from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery
from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.presentation.api.serializers.reset_user_password import (
    ResetUserPasswordSerializer,
)
from src.modules.users.presentation.api.serializers.user import (
    UserListSerializer,
    UserSerializer,
)

from ..dependencies.company_dependencies import (
    get_block_company_user_use_case,
    get_company_users_use_case,
    get_create_company_user_use_case,
    get_reset_company_user_password_use_case,
    get_unblock_company_user_use_case,
)
from ..serializers.company import CreateCompanyUserSerializer
from ._common import error_response, load_actor


def _query_with_shortcuts(request) -> ListQuery:
    """parse_list_query plus ?role=ADMIN and ?is_active=true shortcuts."""
    query = parse_list_query(request.query_params)
    extra = []

    role = request.query_params.get("role")
    if role:
        extra.append(FilterCondition("role", "equals", role.strip().upper()))

    is_active = request.query_params.get("is_active")
    if is_active:
        value = is_active.strip().lower()
        if value not in {"true", "false"}:
            raise ValueError("The is_active parameter must be 'true' or 'false'.")
        extra.append(FilterCondition("is_active", "equals", value == "true"))

    if not extra:
        return query

    return ListQuery(
        filters=query.filters + tuple(extra),
        page=query.page,
        page_size=query.page_size,
        sort_by=query.sort_by,
        sort_direction=query.sort_direction,
        search=query.search,
    )


class CompanyUserListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request, company_id: UUID):
        try:
            result = get_company_users_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                query=_query_with_shortcuts(request),
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {
                "results": UserListSerializer(result.results, many=True).data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, company_id: UUID):
        serializer = CreateCompanyUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = get_create_company_user_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                name=data["name"],
                email=data["email"],
                password=data["password"],
                role=UserRole(data["role"]),
            )
        except ValueError as error:
            return error_response(error)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class CompanyUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, company_id: UUID, user_id: UUID):
        serializer = ResetUserPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            get_reset_company_user_password_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                user_id=user_id,
                new_password=serializer.validated_data["new_password"],
            )
        except ValueError as error:
            return error_response(error)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyUserBlockView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, company_id: UUID, user_id: UUID):
        try:
            user = get_block_company_user_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                user_id=user_id,
            )
        except ValueError as error:
            return error_response(error)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class CompanyUserUnblockView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, company_id: UUID, user_id: UUID):
        try:
            user = get_unblock_company_user_use_case().execute(
                current_user=load_actor(request),
                company_id=company_id,
                user_id=user_id,
            )
        except ValueError as error:
            return error_response(error)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
