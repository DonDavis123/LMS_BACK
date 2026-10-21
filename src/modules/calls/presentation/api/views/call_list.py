from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.tenant import get_tenant_context
from src.modules.calls.application.dto.create_call import CreateCallDTO
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_calls_use_case,
    get_create_call_use_case,
)

from ..serializers.call import CallSerializer
from ..serializers.call_read import CallReadSerializer
from ..serializers.create_call import CreateCallSerializer
from src.modules.shared.presentation.permissions import IsCompanyUser


class CallListView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            result = get_calls_use_case(get_tenant_context(request)).execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CallReadSerializer(result.results, many=True)

        return Response(
            {
                "results": serializer.data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        dto = CreateCallDTO(
            created_by_id=request.user.id,
            call_start_time=data["call_start_time"],
            outcome=CallOutcome(data["outcome"]),
            owner_id=data.get("owner_id"),
            lead_id=data.get("lead_id"),
            contact_id=data.get("contact_id"),
            account_id=data.get("account_id"),
            call_type=CallType(data["call_type"]),
            duration_seconds=data["duration_seconds"],
            description=data.get("description"),
            entry_method=CallEntryMethod(data["entry_method"]),
        )

        try:
            call = get_create_call_use_case(get_tenant_context(request)).execute(dto)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            CallSerializer(call).data,
            status=status.HTTP_201_CREATED,
        )
