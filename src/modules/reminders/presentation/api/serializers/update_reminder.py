from rest_framework import serializers


class UpdateReminderSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255, required=False)
    remind_at = serializers.DateTimeField(required=False)
    task_id = serializers.UUIDField(required=False, allow_null=True)
    meeting_id = serializers.UUIDField(required=False, allow_null=True)
