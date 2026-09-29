from rest_framework import serializers

from src.modules.notifications.domain.enums.notification_type import NotificationType


# Day-level notifications ("meeting today", "task due tomorrow", ...) use the
# local midnight of the relevant day as ``scheduled_for``. That value is only a
# de-duplication key (one notification per record per day). If it is shown to
# the user as the notification time, a notification generated at 12:30 reads as
# "12 hours ago". For these types the user-facing time is when the notification
# was actually generated.
_DAY_LEVEL_TYPES = {
    NotificationType.TASK_DUE_ONE_DAY,
    NotificationType.TASK_DUE_TODAY,
    NotificationType.MEETING_ONE_DAY,
    NotificationType.MEETING_TODAY,
}

_datetime_field = serializers.DateTimeField()


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

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.notification_type in _DAY_LEVEL_TYPES:
            display_at = _datetime_field.to_representation(instance.created_at)
            data["scheduled_for"] = display_at
        else:
            display_at = data["scheduled_for"]

        # Explicit field clients can use for "time ago" / sorting displays.
        data["display_at"] = display_at
        return data
