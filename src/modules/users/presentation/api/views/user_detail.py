from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.application.dto.update_user import UpdateUserDTO
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
    get_delete_user_use_case,
    get_update_user_use_case,
    get_user_details_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.update_user import UpdateUserSerializer
from ..serializers.user import UserSerializer


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, user_id: UUID):
        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            user = get_user_details_use_case().execute(
                current_user=current_user,
                user_id=user_id,
            )
        except ValueError as error:
            return self._error_response(error)

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, user_id: UUID):
        serializer = UpdateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dto = UpdateUserDTO(
            user_id=user_id,
            name=data.get("name"),
            email=data.get("email"),
            role=(
                UserRole(data["role"])
                if data.get("role") is not None
                else None
            ),
        )

        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            user = get_update_user_use_case().execute(
                current_user=current_user,
                data=dto,
            )
        except ValueError as error:
            return self._error_response(error)

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id: UUID):
        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            get_delete_user_use_case().execute(
                current_user=current_user,
                user_id=user_id,
            )
        except ValueError as error:
            return self._error_response(error)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _error_response(error: ValueError):
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
