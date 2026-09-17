from rest_framework import serializers


class TimelineActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class TimelineTargetSerializer(serializers.Serializer):
    entity_type = serializers.CharField()
    entity_id = serializers.UUIDField()


class TimelineEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    actor = TimelineActorSerializer()
    message = serializers.CharField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    targets = TimelineTargetSerializer(many=True)
