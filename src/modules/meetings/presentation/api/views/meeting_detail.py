from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO, _UNSET
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.presentation.api.dependencies.meeting_dependencies import (
    get_delete_meeting_use_case,
    get_meeting_use_case,
    get_update_meeting_use_case,
)

from ..serializers.meeting import MeetingDetailSerializer
from ..serializers.update_meeting import UpdateMeetingSerializer


def _participant_groups(data) -> tuple[ParticipantGroup, ...]:
    groups = []
    mapping = (
        ("leads", MeetingParticipantType.LEAD),
        ("contacts", MeetingParticipantType.CONTACT),
        ("users", MeetingParticipantType.USER),
    )
    for field, participant_type in mapping:
        ids = tuple(data.get(field, []))
        if ids:
            groups.append(ParticipantGroup(participant_type, ids))
    return tuple(groups)


class MeetingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, meeting_id):
        result = get_meeting_use_case().execute(meeting_id)
        if result is None:
            return Response({"detail": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(MeetingDetailSerializer(result).data, status=status.HTTP_200_OK)

    def patch(self, request, meeting_id):
        serializer = UpdateMeetingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        relationship_keys = {"related_to", "participants"}
        fields = {key: value for key, value in data.items() if key not in relationship_keys}

        related_record_type = _UNSET
        related_record_ids = _UNSET
        if "related_to" in data:
            related_to = data["related_to"]
            if related_to is None:
                related_record_type = None
                related_record_ids = ()
            else:
                related_record_type = MeetingRelatedRecordType(related_to["type"])
                related_record_ids = tuple(related_to["ids"])

        participant_groups = _UNSET
        if "participants" in data:
            participants = data["participants"] or {}
            participant_groups = _participant_groups(participants)

        dto = UpdateMeetingDTO(
            meeting_id=meeting_id,
            fields=fields,
            related_record_type=related_record_type,
            related_record_ids=related_record_ids,
            participant_groups=participant_groups,
        )

        try:
            meeting = get_update_meeting_use_case().execute(dto)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"id": str(meeting.id), "message": "Meeting updated successfully."},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, meeting_id):
        try:
            get_delete_meeting_use_case().execute(meeting_id)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": "Meeting deleted successfully."},
            status=status.HTTP_200_OK,
        )
