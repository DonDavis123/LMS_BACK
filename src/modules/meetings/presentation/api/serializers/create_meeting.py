from rest_framework import serializers

from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


class RelatedToRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[(item.value, item.value) for item in MeetingRelatedRecordType]
    )
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )


class ParticipantsRequestSerializer(serializers.Serializer):
    leads = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    contacts = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    users = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )


class CreateMeetingSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    is_all_day = serializers.BooleanField(required=False, default=False)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    host_id = serializers.UUIDField()
    related_to = RelatedToRequestSerializer(required=False, allow_null=True)
    participants = ParticipantsRequestSerializer(required=False)
