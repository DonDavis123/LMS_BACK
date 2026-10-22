from rest_framework import serializers

from .call_read import CallReadSerializer


class _RelatedRecordSerializer(serializers.Serializer):
    type = serializers.CharField(source="related_record_type")
    id = serializers.UUIDField(source="related_record_id")
    name = serializers.CharField(source="related_record_name", allow_null=True)


class _ActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class _ChangeHistoryEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    actor = _ActorSerializer()
    message = serializers.CharField()
    changes = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_changes(self, event):
        # field -> {old_value, new_value}; CALL_LOGGED carries no changes.
        return (event.get("metadata") or {}).get("changes") or {}


class _RelatedCallSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="call.id")
    call_start_time = serializers.DateTimeField(source="call.call_start_time")
    duration_seconds = serializers.IntegerField(source="call.duration_seconds")
    duration_label = serializers.CharField(source="call.duration_label")
    outcome = serializers.CharField(source="call.outcome.value")
    call_type = serializers.CharField(source="call.call_type.value")
    description = serializers.CharField(source="call.description", allow_null=True)
    owner_name = serializers.CharField(allow_null=True)


class CallDetailSerializer(CallReadSerializer):
    """Detail response: every list-row field plus history and sibling calls.

    The input is a ``GetCallDetailDTO``; the inherited list-row fields are
    rendered from its ``call`` (a ``GetCallDTO``).
    """

    def to_representation(self, instance):
        data = super().to_representation(instance.call)

        data["related_record"] = _RelatedRecordSerializer(instance).data
        data["change_history"] = _ChangeHistoryEventSerializer(
            instance.change_history,
            many=True,
        ).data
        data["related_calls"] = _RelatedCallSerializer(
            instance.related_calls,
            many=True,
        ).data
        data["total_calls_for_record"] = instance.total_calls_for_record
        data["is_latest"] = instance.is_latest

        return data
