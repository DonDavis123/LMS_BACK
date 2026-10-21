from datetime import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.calls.application.dto.update_call import UpdateCallDTO
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_call_detail_use_case,
    get_delete_call_use_case,
    get_update_call_use_case,
)

from ..serializers.call import CallSerializer
from ..serializers.call_detail import CallDetailSerializer
from ..serializers.update_call import UpdateCallSerializer
from src.modules.shared.presentation.permissions import IsCompanyUser


class CallDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, call_id):
        call = get_call_detail_use_case(get_tenant_context(request)).execute(call_id)

        if call is None:
            return Response(
                {"detail": "Call not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            CallDetailSerializer(call).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, call_id):
        serializer = UpdateCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fields = dict(serializer.validated_data)

        if "call_type" in fields:
            fields["call_type"] = CallType(fields["call_type"])

        if "outcome" in fields:
            fields["outcome"] = CallOutcome(fields["outcome"])

        if "call_start_time" in fields:
            # Stored values are UTC; normalising keeps an unchanged instant
            # sent with another UTC offset from being logged as a change.
            fields["call_start_time"] = fields["call_start_time"].astimezone(
                timezone.utc
            )

        dto = UpdateCallDTO(
            call_id=call_id,
            fields=fields,
        )

        try:
            call = get_update_call_use_case(get_tenant_context(request)).execute(
                dto,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            if str(error) == "Call not found.":
                return Response(
                    {"detail": "Call not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            CallSerializer(call).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, call_id):
        try:
            get_delete_call_use_case(get_tenant_context(request)).execute(
                call_id,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            if str(error) == "Call not found.":
                return Response(
                    {"detail": "Call not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Call deleted successfully."},
            status=status.HTTP_200_OK,
        )
