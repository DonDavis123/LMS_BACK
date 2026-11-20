from django.conf import settings
from rest_framework import serializers


class DailyBriefingRequestSerializer(serializers.Serializer):
    """Body of POST /dashboard/briefing/ (every field is optional)."""

    tz = serializers.CharField(required=False, default=settings.TIME_ZONE, max_length=64)


class PrioritizedTaskSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    task_id = serializers.UUIDField()
    subject = serializers.CharField()
    priority = serializers.CharField()
    status = serializers.CharField()
    due_date = serializers.DateField(allow_null=True)
    urgency = serializers.CharField()
    days_overdue = serializers.IntegerField()
    related_to = serializers.CharField(allow_null=True)
    bucket = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)


class DailyBriefingCountsSerializer(serializers.Serializer):
    overdue_tasks = serializers.IntegerField()
    due_today_tasks = serializers.IntegerField()
    meetings_today = serializers.IntegerField()
    open_tasks_total = serializers.IntegerField()
    tasks_considered = serializers.IntegerField()


class DailyBriefingSerializer(serializers.Serializer):
    """Serializes a ``DailyBriefingDTO`` into the response body."""

    date = serializers.DateField()
    generated_at = serializers.DateTimeField()
    model_name = serializers.CharField(allow_null=True)
    headline = serializers.CharField()
    counts = DailyBriefingCountsSerializer()
    priorities = PrioritizedTaskSerializer(many=True)
    heads_up = serializers.ListField(child=serializers.CharField())
