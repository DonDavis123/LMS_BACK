from uuid import UUID

from django.http import FileResponse
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.calls.application.dto.call_recording import UploadCallRecordingDTO
from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_delete_call_recording_use_case,
    get_call_recording_file_use_case,
    get_list_call_recordings_use_case,
    get_upload_call_recording_use_case,
    recording_limits,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.call_recording import CallRecordingSerializer
from ..serializers.upload_call_recording import UploadCallRecordingSerializer

# A multipart body is the audio plus a little framing and the small form fields.
MULTIPART_OVERHEAD_BYTES = 64 * 1024

NOT_FOUND_MESSAGES = {
    "Call not found.",
    "Recording not found.",
    "The recording file is no longer available.",
}


class _AnyRendererNegotiation(DefaultContentNegotiation):
    """The file endpoint answers with audio, whatever ``Accept`` says."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


def _error_response(error: ValueError) -> Response:
    message = str(error)

    return Response(
        {"detail": message},
        status=(
            status.HTTP_404_NOT_FOUND
            if message in NOT_FOUND_MESSAGES
            else status.HTTP_400_BAD_REQUEST
        ),
    )


class CallRecordingListView(APIView):
    """``GET`` the recordings of a call, ``POST`` (multipart) to add one."""

    permission_classes = [IsAuthenticated, IsCompanyUser]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, call_id):
        recordings = get_list_call_recordings_use_case(
            get_tenant_context(request)
        ).execute(call_id)

        if recordings is None:
            return Response(
                {"detail": "Call not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"results": CallRecordingSerializer(recordings, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request, call_id):
        max_size_bytes, _ = recording_limits()

        # Refuse a huge body before Django reads it into a temporary file.
        declared = request.META.get("CONTENT_LENGTH")
        if declared and str(declared).isdigit() and (
            int(declared) > max_size_bytes + MULTIPART_OVERHEAD_BYTES
        ):
            return Response(
                {
                    "detail": (
                        "The recording is larger than "
                        f"{max_size_bytes // (1024 * 1024)} MB."
                    )
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        serializer = UploadCallRecordingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        file = data["file"]

        dto = UploadCallRecordingDTO(
            call_id=call_id,
            uploaded_by_id=request.user.id,
            file_name=file.name,
            content_type=file.content_type,
            size_bytes=file.size,
            content=file,
            duration_seconds=data.get("duration_seconds"),
        )

        try:
            recording = get_upload_call_recording_use_case(
                get_tenant_context(request)
            ).execute(dto)
        except ValueError as error:
            return _error_response(error)

        return Response(
            CallRecordingSerializer(recording).data,
            status=status.HTTP_201_CREATED,
        )


class CallRecordingDetailView(APIView):
    """``DELETE`` one recording of a call."""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def delete(self, request, call_id, recording_id):
        try:
            get_delete_call_recording_use_case(
                get_tenant_context(request)
            ).execute(
                call_id,
                recording_id,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            return _error_response(error)

        return Response(
            {"message": "Recording deleted successfully."},
            status=status.HTTP_200_OK,
        )


class CallRecordingFileView(APIView):
    """``GET`` the audio of one recording (``?download=1`` forces a download)."""

    permission_classes = [IsAuthenticated, IsCompanyUser]
    content_negotiation_class = _AnyRendererNegotiation

    def get(self, request, call_id: UUID, recording_id: UUID):
        try:
            file = get_call_recording_file_use_case(
                get_tenant_context(request)
            ).execute(call_id, recording_id)
        except ValueError as error:
            return _error_response(error)

        download = request.query_params.get("download") in {"1", "true"}

        response = FileResponse(
            file.content,
            content_type=file.recording.content_type,
            as_attachment=download,
            filename=file.recording.file_name,
        )
        # The audio is private to the company: never cache it, and never let
        # a browser guess a different type for it.
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"

        return response
