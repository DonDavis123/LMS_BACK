from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.picklists.presentation.api.dependencies.picklist_dependencies import (
    get_create_option_use_case,
)
from src.modules.picklists.presentation.permissions.is_company_superadmin import (
    IsCompanySuperAdmin,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.picklist import (
    CreatePicklistOptionSerializer,
    PicklistOptionSerializer,
)
from ._common import error_response


class CreatePicklistOptionView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser, IsCompanySuperAdmin]

    def post(self, request, module: str, field: str):
        serializer = CreatePicklistOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            option = get_create_option_use_case(get_tenant_context(request)).execute(
                module=module,
                field=field,
                value=serializer.validated_data["value"],
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            PicklistOptionSerializer(
                {
                    "id": option.id,
                    "value": option.value,
                    "sort_order": option.sort_order,
                    "is_active": option.is_active,
                    "is_system": option.is_system,
                    "usage_count": 0,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )
