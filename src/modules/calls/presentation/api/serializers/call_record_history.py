from rest_framework import serializers


class _ActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class _CallSnapshotSerializer(serializers.Serializer):
    """The call as it was when the event happened. Any field may be null."""

    call_start_time = serializers.DateTimeField(allow_null=True)
    call_type = serializers.CharField(allow_null=True)
    outcome = serializers.CharField(allow_null=True)
    duration_seconds = serializers.IntegerField(allow_null=True)
    duration_label = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    owner_name = serializers.CharField(allow_null=True)


class _HistoryEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    call_id = serializers.UUIDField(allow_null=True)
    actor = _ActorSerializer()
    message = serializers.CharField()
    changes = serializers.DictField()
    created_at = serializers.DateTimeField()
    call = _CallSnapshotSerializer()


class _RelatedRecordSerializer(serializers.Serializer):
    type = serializers.CharField(source="related_record_type")
    id = serializers.UUIDField(source="related_record_id")
    name = serializers.CharField(source="related_record_name", allow_null=True)


class CallRecordHistorySerializer(serializers.Serializer):
    """Input: ``GetCallRecordHistoryDTO``."""

    def to_representation(self, instance):
        return {
            "related_record": _RelatedRecordSerializer(instance).data,
            "total_calls_for_record": instance.total_calls_for_record,
            "events": _HistoryEventSerializer(instance.events, many=True).data,
        }
