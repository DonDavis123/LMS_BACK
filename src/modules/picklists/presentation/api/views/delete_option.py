from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.picklists.presentation.api.dependencies.picklist_dependencies import (
    get_delete_option_use_case,
)
from src.modules.picklists.presentation.permissions.is_company_superadmin import (
    IsCompanySuperAdmin,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ._common import error_response


class DeletePicklistOptionView(APIView):
    """DELETE, optionally with ``replace_with=<option id>`` (query or JSON body)."""

    permission_classes = [IsAuthenticated, IsCompanyUser, IsCompanySuperAdmin]

    def delete(self, request, option_id: UUID):
        raw = request.query_params.get("replace_with")
        if raw is None and isinstance(request.data, dict):
            raw = request.data.get("replace_with")

        replace_with = None
        if raw:
            try:
                replace_with = UUID(str(raw))
            except ValueError:
                raise ValidationError({"replace_with": "Must be a valid option id."})

        try:
            moved = get_delete_option_use_case(get_tenant_context(request)).execute(
                option_id=option_id,
                replace_with=replace_with,
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {"message": "Option deleted successfully.", "records_updated": moved},
            status=status.HTTP_200_OK,
        )
