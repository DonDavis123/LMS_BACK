from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.lead_capture.application.dto.lead_form_dto import UpdateLeadFormDTO
from src.modules.lead_capture.presentation.api.dependencies.lead_form_dependencies import (
    get_block_lead_form_use_case,
    get_lead_form_use_case,
    get_regenerate_lead_form_link_use_case,
    get_unblock_lead_form_use_case,
    get_update_lead_form_use_case,
)
from src.modules.lead_capture.presentation.permissions.is_lead_form_manager import (
    IsLeadFormManager,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.lead_form import LeadFormSerializer, UpdateLeadFormSerializer

PERMISSIONS = [IsAuthenticated, IsCompanyUser, IsLeadFormManager]


def _bad_request(error: ValueError) -> Response:
    return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


class LeadFormView(APIView):
    permission_classes = PERMISSIONS

    def get(self, request):
        form = get_lead_form_use_case(get_tenant_context(request)).execute()
        return Response(LeadFormSerializer(form).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UpdateLeadFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Only what the client sent is passed on; the rest stays untouched.
        data = serializer.validated_data
        changes = {
            name: data[name]
            for name in (
                "title",
                "lead_source",
                "assignment_mode",
                "single_owner_id",
                "rotation_owner_ids",
            )
            if name in data
        }

        try:
            form = get_update_lead_form_use_case(get_tenant_context(request)).execute(
                UpdateLeadFormDTO(**changes)
            )
        except ValueError as error:
            return _bad_request(error)

        return Response(LeadFormSerializer(form).data, status=status.HTTP_200_OK)


class _FormActionView(APIView):
    permission_classes = PERMISSIONS
    use_case_factory = None

    def post(self, request):
        try:
            form = type(self).use_case_factory(get_tenant_context(request)).execute()
        except ValueError as error:
            return _bad_request(error)
        return Response(LeadFormSerializer(form).data, status=status.HTTP_200_OK)


class BlockLeadFormView(_FormActionView):
    use_case_factory = staticmethod(get_block_lead_form_use_case)


class UnblockLeadFormView(_FormActionView):
    use_case_factory = staticmethod(get_unblock_lead_form_use_case)


class RegenerateLeadFormLinkView(_FormActionView):
    use_case_factory = staticmethod(get_regenerate_lead_form_link_use_case)
