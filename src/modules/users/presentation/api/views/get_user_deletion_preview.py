from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
    get_user_deletion_preview_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.user_deletion_preview import UserDeletionPreviewSerializer


class UserDeletionPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser, IsSuperAdmin]

    def get(self, request, user_id: UUID):
        ctx = get_tenant_context(request)
        try:
            current_user = get_current_user_use_case(ctx).execute(
                user_id=request.user.id,
            )
            preview = get_user_deletion_preview_use_case(ctx).execute(
                current_user=current_user,
                user_id=user_id,
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

        return Response(
            UserDeletionPreviewSerializer(preview).data,
            status=status.HTTP_200_OK,
        )
