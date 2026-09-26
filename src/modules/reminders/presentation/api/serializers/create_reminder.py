from rest_framework import serializers


class CreateReminderSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    remind_at = serializers.DateTimeField()
    task_id = serializers.UUIDField(required=False, allow_null=True)
    meeting_id = serializers.UUIDField(required=False, allow_null=True)
