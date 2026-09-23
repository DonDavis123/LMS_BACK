from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.presentation.api.cookies import (
    clear_refresh_token_cookie,
    get_refresh_token,
)
from src.modules.authentication.presentation.api.dependencies.authentication_dependencies import (
    get_logout_user_use_case,
)


class LogoutView(APIView):

    def post(self, request):
        refresh_token = get_refresh_token(request)

        use_case = get_logout_user_use_case()
        use_case.execute(refresh_token)

        response = Response(status=status.HTTP_204_NO_CONTENT)

        clear_refresh_token_cookie(request, response)

        return response
