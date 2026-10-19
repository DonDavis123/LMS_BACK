from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.picklists.presentation.api.dependencies.picklist_dependencies import (
    get_picklists_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.users.domain.entities.role import UserRole

from ..serializers.picklist import PicklistFieldSerializer
from ._common import error_response


def _wants_admin_view(request) -> bool:
    return request.query_params.get("include_inactive", "").lower() in {
        "1",
        "true",
        "yes",
    }


class GetModulePicklistsView(APIView):
    """Every customisable dropdown of a module (used to fill the forms).

    Any company user can read the *active* options. Hidden options and
    usage counts (``?include_inactive=true``) are for superadmins only.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, module: str):
        return _respond(request, module, None)


class GetFieldPicklistView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, module: str, field: str):
        return _respond(request, module, field)


def _respond(request, module: str, field: str | None):
    include_inactive = _wants_admin_view(request)
    if include_inactive and request.user.role != UserRole.SUPERADMIN.value:
        raise PermissionDenied(
            "Only company superadmins can see hidden options."
        )

    try:
        fields = get_picklists_use_case(get_tenant_context(request)).execute(
            module=module,
            field=field,
            include_inactive=include_inactive,
        )
    except ValueError as error:
        return error_response(error)

    data = PicklistFieldSerializer(fields, many=True).data
    if field:
        return Response(data[0], status=status.HTTP_200_OK)
    return Response({"module": module, "fields": data}, status=status.HTTP_200_OK)
