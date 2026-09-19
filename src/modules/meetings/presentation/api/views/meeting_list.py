from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.meetings.application.dto.create_meeting import CreateMeetingDTO
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.presentation.api.dependencies.meeting_dependencies import (
    get_create_meeting_use_case,
    get_meetings_use_case,
)
from src.modules.shared.presentation.query_params import parse_list_query

from ..serializers.create_meeting import CreateMeetingSerializer
from ..serializers.meeting import MeetingListSerializer


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


class MeetingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            if query.filters:
                raise ValueError("Meeting filtering is not supported.")
            result = get_meetings_use_case().execute(query)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = MeetingListSerializer(result.results, many=True)
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
        serializer = CreateMeetingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        related_to = data.get("related_to")
        related_record_type = None
        related_record_ids = ()
        if related_to is not None:
            related_record_type = MeetingRelatedRecordType(related_to["type"])
            related_record_ids = tuple(related_to["ids"])

        participants = data.get("participants") or {}
        dto = CreateMeetingDTO(
            title=data["title"],
            start_at=data["start_at"],
            end_at=data["end_at"],
            host_id=data["host_id"],
            created_by_id=request.user.id,
            description=data.get("description"),
            location=data.get("location"),
            is_all_day=data.get("is_all_day", False),
            related_record_type=related_record_type,
            related_record_ids=related_record_ids,
            participant_groups=_participant_groups(participants),
        )

        try:
            meeting = get_create_meeting_use_case().execute(dto)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"id": str(meeting.id), "message": "Meeting created successfully."},
            status=status.HTTP_201_CREATED,
        )
