from rest_framework import serializers

from src.modules.meetings.application.dto.get_meeting import GetMeetingDTO
from src.modules.meetings.application.dto.get_meetings import GetMeetingsDTO


class MeetingListSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    related_to_type = serializers.SerializerMethodField()
    related_to_names = serializers.ListField(child=serializers.CharField())
    contact_names = serializers.ListField(child=serializers.CharField())
    host_id = serializers.UUIDField()
    host_name = serializers.CharField()

    def get_related_to_type(self, obj: GetMeetingsDTO):
        return obj.related_to_type.value if obj.related_to_type else None


class MeetingRelatedRecordSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    record_type = serializers.SerializerMethodField()
    name = serializers.CharField()

    def get_record_type(self, obj):
        return obj.record_type.value


class MeetingParticipantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    participant_type = serializers.SerializerMethodField()
    name = serializers.CharField()

    def get_participant_type(self, obj):
        return obj.participant_type.value


class MeetingDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="meeting.id")
    title = serializers.CharField(source="meeting.title")
    description = serializers.CharField(source="meeting.description", allow_null=True)
    location = serializers.CharField(source="meeting.location", allow_null=True)
    is_all_day = serializers.BooleanField(source="meeting.is_all_day")
    start_at = serializers.DateTimeField(source="meeting.start_at")
    end_at = serializers.DateTimeField(source="meeting.end_at")
    host = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="meeting.created_at")
    updated_at = serializers.DateTimeField(source="meeting.updated_at")
    related_to = MeetingRelatedRecordSerializer(many=True)
    participants = MeetingParticipantSerializer(many=True)

    def get_host(self, obj: GetMeetingDTO):
      return {
        "id": str(obj.host_id),
        "name": obj.host_name,
    }

    def get_created_by(self, obj: GetMeetingDTO):
      return {
        "id": str(obj.created_by_id),
        "name": obj.created_by_name,
    }


class MeetingWriteResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    message = serializers.CharField()
