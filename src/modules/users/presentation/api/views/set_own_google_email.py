from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_set_own_google_email_use_case,
)

from ..current_user_payload import build_current_user_payload
from ..serializers.set_own_google_email import SetOwnGoogleEmailSerializer


class SetOwnGoogleEmailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def patch(self, request):
        ctx = get_tenant_context(request)
        serializer = SetOwnGoogleEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = get_set_own_google_email_use_case(ctx).execute(
                user_id=request.user.id,
                google_email=serializer.validated_data["google_email"],
            )
        except ValueError as error:
            message = str(error)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if message.endswith("not found.")
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {"detail": message},
                status=status_code,
            )

        return Response(
            build_current_user_payload(user),
            status=status.HTTP_200_OK,
        )
