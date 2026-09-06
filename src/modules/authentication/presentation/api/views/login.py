from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.domain.exceptions import (
    InvalidCredentialsError,
    InactiveUserError,
)

from src.modules.authentication.presentation.api.dependencies.authentication_dependencies import (
    get_login_user_use_case,
)

from ..serializer.login import LoginSerializer


class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = get_login_user_use_case()

        try:
            result = use_case.execute(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            )

        except InvalidCredentialsError:
            return Response(
                {
                    "detail": "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except InactiveUserError:
            return Response(
                {
                    "detail": "User account is inactive."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": "Bearer",
            },
            status=status.HTTP_200_OK,
        )