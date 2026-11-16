from rest_framework import serializers

from .related_to import RelatedToGroupSerializer, RelatedToSerializerMixin


class ParticipantsUpdateSerializer(serializers.Serializer):
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


class UpdateMeetingSerializer(RelatedToSerializerMixin, serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    is_all_day = serializers.BooleanField(required=False)
    start_at = serializers.DateTimeField(required=False)
    end_at = serializers.DateTimeField(required=False)
    reminder_at = serializers.DateTimeField(required=False, allow_null=True)
    host_id = serializers.UUIDField(required=False)
    send_email_notifications = serializers.BooleanField(required=False)
    reminder_offsets = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
    )
    reminder_subject = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    reminder_message = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    related_to = RelatedToGroupSerializer(many=True, required=False, allow_null=True)
    participants = ParticipantsUpdateSerializer(required=False, allow_null=True)
