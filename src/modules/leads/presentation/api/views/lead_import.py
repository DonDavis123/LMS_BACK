from uuid import UUID

from django.http import HttpResponse
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.services.lead_import_parser import ImportFileError
from src.modules.leads.application.services.lead_import_review import import_limits
from src.modules.leads.application.use_cases.lead_import_common import ImportRequestError
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_discard_import_draft_use_case,
    get_import_template_use_case,
    get_list_import_rows_use_case,
    get_preview_import_mapping_use_case,
    get_update_import_exclusions_use_case,
    get_upload_import_file_use_case,
    get_validate_import_use_case,
)
from src.modules.leads.presentation.permissions.can_import_leads import CanImportLeads
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

# A multipart body is the file plus a little framing and the small form fields.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


class _AnyRendererNegotiation(DefaultContentNegotiation):
    """The template endpoint answers with a file. DRF would otherwise read
    ``?format=csv`` as a renderer name and answer 404."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


def _problem(error) -> Response:
    """``{detail, code, how_to_fix}`` for a request or file problem."""
    code = getattr(error, "status_code", status.HTTP_400_BAD_REQUEST)
    return Response(error.to_dict(), status=code)


class _ImportView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser, CanImportLeads]

    @staticmethod
    def _body_part(request, name):
        data = request.data
        if not hasattr(data, "get"):
            raise ImportRequestError(
                "invalid_request",
                "The request body must be a JSON object.",
                "Send a JSON body such as {\"mapping\": {...}, \"options\": {...}}.",
            )
        return data.get(name)


class ImportTemplateView(_ImportView):
    content_negotiation_class = _AnyRendererNegotiation

    def get(self, request):
        try:
            file = get_import_template_use_case().execute(
                request.query_params.get("format")
            )
        except ImportRequestError as error:
            return _problem(error)

        response = HttpResponse(file.content, content_type=file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{file.file_name}"'
        response["Cache-Control"] = "no-store"
        return response


class ImportUploadView(_ImportView):

    def post(self, request):
        limits = import_limits()
        # Refuse a huge body before Django reads it into a temporary file.
        declared = request.META.get("CONTENT_LENGTH")
        if declared and str(declared).isdigit() and (
            int(declared) > limits["max_bytes"] + MULTIPART_OVERHEAD_BYTES
        ):
            error = ImportFileError(
                "file_too_large",
                f"The file is larger than {limits['max_bytes'] // (1024 * 1024)} MB.",
                "Split the file into smaller files, or remove unused columns and sheets, "
                "and upload again.",
            )
            return _problem(error)

        file = request.FILES.get("file")
        form = request.data if hasattr(request.data, "get") else {}
        try:
            result = get_upload_import_file_use_case(get_tenant_context(request)).execute(
                file,
                getattr(file, "name", None),
                header_row=form.get("header_row"),
                sheet_name=form.get("sheet_name"),
            )
        except ImportFileError as error:
            return _problem(error)

        return Response(result, status=status.HTTP_201_CREATED)


class ImportMappingPreviewView(_ImportView):

    def post(self, request, job_id):
        try:
            result = get_preview_import_mapping_use_case(
                get_tenant_context(request)
            ).execute(
                UUID(str(job_id)),
                self._body_part(request, "mapping"),
                self._body_part(request, "options"),
            )
        except ImportRequestError as error:
            return _problem(error)
        return Response(result, status=status.HTTP_200_OK)


class ImportValidateView(_ImportView):

    def post(self, request, job_id):
        try:
            result = get_validate_import_use_case(get_tenant_context(request)).execute(
                UUID(str(job_id)),
                self._body_part(request, "mapping"),
                self._body_part(request, "options"),
            )
        except ImportRequestError as error:
            return _problem(error)
        return Response(result, status=status.HTTP_200_OK)


class ImportRowsView(_ImportView):

    def get(self, request, job_id):
        params = request.query_params
        try:
            result = get_list_import_rows_use_case(get_tenant_context(request)).execute(
                UUID(str(job_id)),
                status=params.get("status"),
                page=params.get("page"),
                page_size=params.get("page_size"),
                q=params.get("q"),
            )
        except ImportRequestError as error:
            return _problem(error)
        return Response(result, status=status.HTTP_200_OK)


class ImportExclusionsView(_ImportView):

    def patch(self, request, job_id):
        try:
            result = get_update_import_exclusions_use_case(
                get_tenant_context(request)
            ).execute(UUID(str(job_id)), request.data if hasattr(request.data, "get") else None)
        except ImportRequestError as error:
            return _problem(error)
        return Response(result, status=status.HTTP_200_OK)


class ImportDraftView(_ImportView):

    def delete(self, request, job_id):
        try:
            get_discard_import_draft_use_case(get_tenant_context(request)).execute(
                UUID(str(job_id))
            )
        except ImportRequestError as error:
            return _problem(error)
        return Response(status=status.HTTP_204_NO_CONTENT)
