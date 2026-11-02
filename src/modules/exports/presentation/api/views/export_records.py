from django.http import Http404, StreamingHttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.application.authorization.lead_permissions import (
    LeadPermissions,
)
from src.modules.exports.presentation.api.dependencies.export_dependencies import (
    get_export_definition,
    get_export_records_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.query_params import parse_list_query
from src.modules.shared.presentation.tenant import get_tenant_context


class _AnyRendererNegotiation(DefaultContentNegotiation):
    """The endpoint answers with a file. DRF would otherwise read
    ``?format=csv`` as a renderer name and answer 404."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class ExportRecordsView(APIView):
    """``GET /api/exports/<entity>/?format=csv|xlsx`` plus the same ``search``,
    ``filters``, ``sort_by`` and ``sort_direction`` parameters as the list."""

    permission_classes = [IsAuthenticated, IsCompanyUser]
    content_negotiation_class = _AnyRendererNegotiation

    def get(self, request, entity):
        definition = get_export_definition(entity)
        if definition is None:
            raise Http404("Unknown export.")

        ctx = get_tenant_context(request)

        # Same rule as the lead list: only admins may read all leads.
        if entity == "leads" and not LeadPermissions.can_view_all_leads(request.user):
            raise PermissionDenied("You do not have permission to export leads.")

        try:
            query = parse_list_query(request.query_params)
            download = get_export_records_use_case(entity, ctx).execute(
                query,
                request.query_params.get("format"),
                timezone.localtime(),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = StreamingHttpResponse(
            download.stream,
            content_type=download.stream.content_type,
        )
        response["Content-Disposition"] = content_disposition_header(
            True, download.file_name
        )
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
