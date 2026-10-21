from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_call_records_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.call_record import CallRecordSerializer


class CallRecordListView(APIView):
    """``GET /calls/records/`` — one row per lead / contact."""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            result = get_call_records_use_case(get_tenant_context(request)).execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "results": CallRecordSerializer(result.results, many=True).data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )
