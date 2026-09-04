from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.application.use_cases.refreshtoken import (
    RefreshTokenUseCase,
)
from src.modules.authentication.infrastructure.security.jwt_token_service import (
    JWTTokenService,
)

from ..serializer.refresh_token import RefreshTokenSerializer


class RefreshTokenView(APIView):

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]

        use_case = RefreshTokenUseCase(
            token_service=JWTTokenService(),
        )

        try:
            tokens = use_case.execute(refresh_token)

        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            tokens,
            status=status.HTTP_200_OK,
        )