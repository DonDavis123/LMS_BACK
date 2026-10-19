from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.picklists.application.use_cases.update_option import _UNSET
from src.modules.picklists.presentation.api.dependencies.picklist_dependencies import (
    get_update_option_use_case,
)
from src.modules.picklists.presentation.permissions.is_company_superadmin import (
    IsCompanySuperAdmin,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.picklist import (
    PicklistOptionSerializer,
    UpdatePicklistOptionSerializer,
)
from ._common import error_response


class UpdatePicklistOptionView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser, IsCompanySuperAdmin]

    def patch(self, request, option_id: UUID):
        serializer = UpdatePicklistOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            option = get_update_option_use_case(get_tenant_context(request)).execute(
                option_id=option_id,
                value=data.get("value", _UNSET),
                is_active=data.get("is_active", _UNSET),
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
                    "usage_count": None,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
