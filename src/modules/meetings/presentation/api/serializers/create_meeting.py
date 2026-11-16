from rest_framework import serializers

from .related_to import RelatedToGroupSerializer, RelatedToSerializerMixin


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


class CreateMeetingSerializer(RelatedToSerializerMixin, serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    is_all_day = serializers.BooleanField(required=False, default=False)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    reminder_at = serializers.DateTimeField(required=False, allow_null=True)
    host_id = serializers.UUIDField()
    related_to = RelatedToGroupSerializer(many=True, required=False, allow_null=True)
    participants = ParticipantsRequestSerializer(required=False)
    add_google_meet = serializers.BooleanField(required=False, default=False)
    # Email invitations/updates/cancellations and the reminder before the
    # meeting, with or without Google Meet. Omitted: follows add_google_meet.
    send_email_notifications = serializers.BooleanField(
        required=False, allow_null=True, default=None
    )
    # Minutes before the start: any of 1440 (1 day), 60, 30, 15. [] = none.
    reminder_offsets = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
        default=None,
    )
    # Optional custom reminder email (defaults: title / description).
    reminder_subject = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    reminder_message = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
