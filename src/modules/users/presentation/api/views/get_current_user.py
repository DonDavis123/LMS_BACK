from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
)

from ..current_user_payload import build_current_user_payload


class GetCurrentUserView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        use_case = get_current_user_use_case()

        try:
            user = use_case.execute(
                user_id=request.user.id,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            build_current_user_payload(user),
            status=status.HTTP_200_OK,
        )
