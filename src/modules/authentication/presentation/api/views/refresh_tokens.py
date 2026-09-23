from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.domain.exceptions import (
    InvalidRefreshTokenError,
)
from src.modules.authentication.presentation.api.cookies import (
    get_refresh_token,
    set_refresh_token_cookie,
)
from src.modules.authentication.presentation.api.dependencies.authentication_dependencies import (
    get_refresh_token_use_case,
)


class RefreshTokenView(APIView):

    def post(self, request):
        refresh_token = get_refresh_token(request)

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is missing."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        use_case = get_refresh_token_use_case()

        try:
            tokens = use_case.execute(refresh_token)

        except InvalidRefreshTokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response(
            {
                "access_token": tokens["access_token"],
                "token_type": "Bearer",
            },
            status=status.HTTP_200_OK,
        )

        # The refresh token is never returned to JavaScript.
        # Rotation replaces the old HttpOnly cookie with the new one.
        # Cookie security is selected automatically from the request.
        set_refresh_token_cookie(
            request,
            response,
            tokens["refresh_token"],
        )

        return response
