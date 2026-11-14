from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.meetings.application.interfaces.video_conference_provider import (
    VideoConferenceNotConnectedError,
)
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus
from src.modules.meetings.presentation.api.dependencies.meeting_dependencies import (
    get_add_meeting_conference_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.meeting import MeetingConferenceSerializer


class MeetingConferenceView(APIView):
    """Add Google Meet to an existing meeting, or retry a failed attempt."""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request, meeting_id):
        try:
            meeting = get_add_meeting_conference_use_case(get_tenant_context(request)).execute(
                meeting_id,
                current_user_id=request.user.id,
            )
        except VideoConferenceNotConnectedError as error:
            return Response(
                {"detail": str(error), "code": "google_not_connected"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as error:
            code = (
                status.HTTP_404_NOT_FOUND
                if str(error) == "Meeting not found."
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": str(error)}, status=code)

        data = MeetingConferenceSerializer(meeting).data

        if meeting.conference_status == ConferenceStatus.FAILED:
            # The failure is saved on the meeting; the client can retry.
            return Response(
                {"detail": meeting.conference_error or "Google Meet could not be created.", **data},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"message": "Google Meet is set up for this meeting.", **data},
            status=status.HTTP_200_OK,
        )
