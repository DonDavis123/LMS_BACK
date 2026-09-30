from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_create_user_use_case,
    get_current_user_use_case,
    get_users_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.create_user_serializer import CreateUserSerializer
from ..serializers.user import UserSerializer


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            query = parse_list_query(request.query_params)
            result = get_users_use_case().execute(
                current_user=current_user,
                query=query,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = UserListSerializer(result.results, many=True)

        return Response(
            {
                "results": serializer.data,
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
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            user = get_create_user_use_case().execute(
                current_user=current_user,
                name=data["name"],
                email=data["email"],
                password=data["password"],
                role=UserRole(data["role"]),
            )
        except ValueError as error:
            message = str(error)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if message == "User not found."
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {"detail": message},
                status=status_code,
            )

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )
