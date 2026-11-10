from rest_framework import serializers


class CalendarEventSerializer(serializers.Serializer):
    """Normalised calendar item built from a ``CalendarEventDTO``."""

    id = serializers.UUIDField()
    type = serializers.CharField()
    title = serializers.CharField()
    # A datetime for timed items, a plain date for all-day tasks.
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    all_day = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    owner_id = serializers.UUIDField(allow_null=True)
    owner_name = serializers.CharField(allow_null=True)
    related_record_type = serializers.CharField(allow_null=True)
    related_record_id = serializers.UUIDField(allow_null=True)
    related_record_name = serializers.CharField(allow_null=True)
    reminder_at = serializers.DateTimeField(allow_null=True)

    @staticmethod
    def _iso(value):
        return value.isoformat() if value is not None else None

    def get_start(self, event):
        return self._iso(event.start)

    def get_end(self, event):
        return self._iso(event.end)
