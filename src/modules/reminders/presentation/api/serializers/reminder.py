from rest_framework import serializers


class ReminderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    subject = serializers.CharField()
    remind_at = serializers.DateTimeField()
    user_id = serializers.UUIDField()
    task_id = serializers.UUIDField(allow_null=True)
    meeting_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
