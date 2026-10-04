from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
    get_reset_user_password_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.reset_user_password import ResetUserPasswordSerializer


class ResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, user_id: UUID):
        serializer = ResetUserPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            get_reset_user_password_use_case().execute(
                current_user=current_user,
                user_id=user_id,
                new_password=serializer.validated_data["new_password"],
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

        return Response(status=status.HTTP_204_NO_CONTENT)
