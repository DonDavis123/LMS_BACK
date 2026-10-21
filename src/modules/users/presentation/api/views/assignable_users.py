from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_assignable_users_use_case,
)

from ..serializers.assignable_user import AssignableUserSerializer


class GetAssignableUsersView(APIView):
    """Dropdown source for "Assigned To": active users of the caller's company."""

    permission_classes = [
        IsAuthenticated,
        IsCompanyUser,
    ]

    def get(self, request):
        ctx = get_tenant_context(request)

        use_case = get_assignable_users_use_case(ctx)

        users = use_case.execute()

        serializer = AssignableUserSerializer(
            users,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
