from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.presentation.api.dependencies.authentication_dependencies import (
    get_forgot_password_use_case,
)

from ..serializer.forgot_password import ForgotPasswordSerializer


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        use_case = get_forgot_password_use_case()

        use_case.execute(
            email=serializer.validated_data["email"],
        )

        return Response(
            {
                "detail": (
                    "If an account exists with this email, "
                    "a password reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )