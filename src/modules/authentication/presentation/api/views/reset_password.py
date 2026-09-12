from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.application.dto.reset_password import (
    ResetPasswordDTO,
)
from src.modules.authentication.presentation.api.dependencies.authentication_dependencies import (
    get_reset_password_use_case,
)

from ..serializer.reset_password import ResetPasswordSerializer


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        dto = ResetPasswordDTO(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )

        use_case = get_reset_password_use_case()

        try:
            use_case.execute(data=dto)

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "detail": "Password has been reset successfully.",
            },
            status=status.HTTP_200_OK,
        )