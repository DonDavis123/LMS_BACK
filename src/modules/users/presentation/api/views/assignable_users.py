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
    """Dropdown source for "Assigned To": active users of the caller's company.

    ``?exclude_self=true`` leaves the logged-in user out (a task cannot be
    assigned to yourself); without it every active company user is listed.
    """

    permission_classes = [
        IsAuthenticated,
        IsCompanyUser,
    ]

    def get(self, request):
        ctx = get_tenant_context(request)

        use_case = get_assignable_users_use_case(ctx)

        exclude_self = request.query_params.get("exclude_self", "").lower() in {
            "1",
            "true",
            "yes",
        }

        users = use_case.execute(
            exclude_user_id=request.user.id if exclude_self else None,
        )

        serializer = AssignableUserSerializer(
            users,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
