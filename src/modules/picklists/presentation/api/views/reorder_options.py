from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.picklists.presentation.api.dependencies.picklist_dependencies import (
    get_reorder_options_use_case,
)
from src.modules.picklists.presentation.permissions.is_company_superadmin import (
    IsCompanySuperAdmin,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.picklist import ReorderPicklistOptionsSerializer
from ._common import error_response


class ReorderPicklistOptionsView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser, IsCompanySuperAdmin]

    def put(self, request, module: str, field: str):
        serializer = ReorderPicklistOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            get_reorder_options_use_case(get_tenant_context(request)).execute(
                module=module,
                field=field,
                ordered_ids=list(serializer.validated_data["ordered_ids"]),
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {"message": "Order saved successfully."},
            status=status.HTTP_200_OK,
        )
