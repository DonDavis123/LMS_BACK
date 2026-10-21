from rest_framework import serializers

from .call_read import CallReadSerializer


class _ActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class _LatestUpdateSerializer(serializers.Serializer):
    """The newest call event on a lead/contact (logged, edited or deleted)."""

    id = serializers.UUIDField()
    event_type = serializers.CharField()
    actor = _ActorSerializer()
    message = serializers.CharField()
    call_id = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_call_id(self, event):
        return (event.get("metadata") or {}).get("call_id")

    def get_changes(self, event):
        # field -> {old_value, new_value}; empty for CALL_LOGGED / CALL_DELETED.
        return (event.get("metadata") or {}).get("changes") or {}


class CallRecordSerializer(serializers.Serializer):
    """One row of ``GET /calls/records/`` (input: ``GetCallRecordDTO``)."""

    record_type = serializers.CharField()
    record_id = serializers.UUIDField()
    record_name = serializers.CharField(allow_null=True)
    call_count = serializers.IntegerField()
    last_updated_at = serializers.DateTimeField()
    latest_call = serializers.SerializerMethodField()
    latest_update = serializers.SerializerMethodField()

    def get_latest_call(self, row):
        return CallReadSerializer(row.latest_call).data

    def get_latest_update(self, row):
        if row.latest_update is None:
            return None
        return _LatestUpdateSerializer(row.latest_update).data
