from rest_framework import serializers


class LeadSummarySerializer(serializers.Serializer):
    lead_id = serializers.UUIDField()
    headline = serializers.CharField()
    key_points = serializers.ListField(child=serializers.CharField())
    next_steps = serializers.ListField(child=serializers.CharField())
    generated_at = serializers.DateTimeField()
    model_name = serializers.CharField(allow_null=True)
    timeline_events_used = serializers.IntegerField()
    calls_used = serializers.IntegerField()
