from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.shared.presentation.permissions import IsPlatformSuperAdmin
from src.modules.shared.presentation.query_params import parse_list_query

from ..dependencies.company_dependencies import get_platform_audit_logs_use_case
from ..serializers.company import PlatformAuditLogSerializer
from ._common import error_response, load_actor


class PlatformAuditLogListView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)

            company_id = None
            raw_company_id = request.query_params.get("company_id")
            if raw_company_id:
                try:
                    company_id = UUID(raw_company_id)
                except ValueError:
                    raise ValueError("The company_id parameter must be a valid UUID.")

            action = None
            raw_action = request.query_params.get("action")
            if raw_action:
                try:
                    action = PlatformAuditAction(raw_action.strip().upper())
                except ValueError:
                    raise ValueError("The action parameter is not a valid action.")

            result = get_platform_audit_logs_use_case().execute(
                current_user=load_actor(request),
                query=query,
                company_id=company_id,
                action=action,
            )
        except ValueError as error:
            return error_response(error)

        return Response(
            {
                "results": PlatformAuditLogSerializer(result.results, many=True).data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )
