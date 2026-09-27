from rest_framework import serializers


class NotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    notification_type = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    user_id = serializers.UUIDField()
    task_id = serializers.UUIDField(allow_null=True)
    meeting_id = serializers.UUIDField(allow_null=True)
    reminder_id = serializers.UUIDField(allow_null=True)
    scheduled_for = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    dismissed_at = serializers.DateTimeField(allow_null=True)
