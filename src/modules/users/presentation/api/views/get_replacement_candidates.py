from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
    get_replacement_candidates_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.replacement_candidate import ReplacementCandidateSerializer


class UserReplacementCandidatesView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request, user_id: UUID):
        try:
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            candidates = get_replacement_candidates_use_case().execute(
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
            ReplacementCandidateSerializer(candidates, many=True).data,
            status=status.HTTP_200_OK,
        )
