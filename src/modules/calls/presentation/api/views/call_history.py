from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_call_record_history_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.call_record_history import CallRecordHistorySerializer


class CallRecordHistoryView(APIView):
    """``GET /calls/<call_id>/history/`` — every call event on the same lead/contact."""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, call_id):
        history = get_call_record_history_use_case(get_tenant_context(request)).execute(call_id)

        if history is None:
            return Response(
                {"detail": "Call not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            CallRecordHistorySerializer(history).data,
            status=status.HTTP_200_OK,
        )
