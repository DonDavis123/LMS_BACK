from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.calls.application.dto.call_recording_transcript import (
    RequestTranscriptionDTO,
)
from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionUnavailableError,
)
from src.modules.calls.presentation.api.dependencies.call_dependencies import (
    get_recording_transcript_use_case,
    get_request_recording_transcription_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.call_recording_transcript import (
    RecordingTranscriptSerializer,
    RequestTranscriptionSerializer,
)

NOT_FOUND_MESSAGES = {"Call not found.", "Recording not found."}


def _not_found_or_bad_request(error: ValueError) -> Response:
    message = str(error)

    return Response(
        {"detail": message},
        status=(
            status.HTTP_404_NOT_FOUND
            if message in NOT_FOUND_MESSAGES
            else status.HTTP_400_BAD_REQUEST
        ),
    )


class CallRecordingTranscriptView(APIView):
    """``GET`` the transcript + summary of a recording, ``POST`` to (re)generate it."""

    permission_classes = [IsAuthenticated, IsCompanyUser]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, call_id, recording_id):
        try:
            result = get_recording_transcript_use_case(
                get_tenant_context(request)
            ).execute(call_id, recording_id)
        except ValueError as error:
            return _not_found_or_bad_request(error)

        return Response(
            RecordingTranscriptSerializer(result).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, call_id, recording_id):
        serializer = RequestTranscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        context = get_tenant_context(request)

        try:
            result = get_request_recording_transcription_use_case(context).execute(
                RequestTranscriptionDTO(
                    call_id=call_id,
                    recording_id=recording_id,
                    requested_by_id=request.user.id,
                    regenerate=serializer.validated_data["regenerate"],
                )
            )
        except TranscriptionUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as error:
            return _not_found_or_bad_request(error)

        # 202: the work happens in the background, poll the GET endpoint.
        # 200: a finished (or failed) transcript is already there.
        active = result.transcript is not None and result.transcript.status.is_active

        return Response(
            RecordingTranscriptSerializer(result).data,
            status=status.HTTP_202_ACCEPTED if active else status.HTTP_200_OK,
        )
