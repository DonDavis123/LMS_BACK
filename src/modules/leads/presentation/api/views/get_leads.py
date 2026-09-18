from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_leads_use_case,
)
from src.modules.leads.presentation.api.serializers import LeadSerializer
from src.modules.leads.presentation.permissions.is_admin import IsAdmin
from src.modules.shared.presentation.query_params import parse_list_query


class GetLeadsView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            result = get_leads_use_case().execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LeadSerializer(result.results, many=True)

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
