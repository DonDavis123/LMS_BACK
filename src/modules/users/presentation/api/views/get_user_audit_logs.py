from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_current_user_use_case,
    get_user_audit_logs_use_case,
)
from src.modules.users.presentation.permissions.is_superadmin import IsSuperAdmin

from ..serializers.user_audit_log import UserAuditLogSerializer


class UserAuditLogListView(APIView):
    """GET /api/users/audit-logs/?user_id=<uuid>&action=<ACTION>&page=1"""

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        try:
            target_user_id = self._parse_user_id(request.query_params.get("user_id"))
            action = self._parse_action(request.query_params.get("action"))
            query = parse_list_query(request.query_params)
            current_user = get_current_user_use_case().execute(
                user_id=request.user.id,
            )
            result = get_user_audit_logs_use_case().execute(
                current_user=current_user,
                query=query,
                target_user_id=target_user_id,
                action=action,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "results": UserAuditLogSerializer(result.results, many=True).data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _parse_user_id(value: str | None) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(value)
        except ValueError:
            raise ValueError("user_id must be a valid UUID.")

    @staticmethod
    def _parse_action(value: str | None) -> UserAuditAction | None:
        if not value:
            return None
        try:
            return UserAuditAction(value)
        except ValueError:
            raise ValueError("action is not a valid audit action.")
