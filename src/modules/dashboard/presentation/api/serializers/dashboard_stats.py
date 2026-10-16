from django.conf import settings
from rest_framework import serializers


class DashboardStatsQuerySerializer(serializers.Serializer):
    """Query string of GET /dashboard/stats/."""

    range = serializers.IntegerField(required=False, default=30)
    tz = serializers.CharField(required=False, default=settings.TIME_ZONE, max_length=64)


class StatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class SourceCountSerializer(serializers.Serializer):
    source = serializers.CharField()
    count = serializers.IntegerField()


class DailyCountSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class DashboardLeadsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    new_in_range = serializers.IntegerField()
    new_previous_range = serializers.IntegerField()
    converted = serializers.IntegerField()
    by_status = StatusCountSerializer(many=True)
    by_source = SourceCountSerializer(many=True)
    created_per_day = DailyCountSerializer(many=True)


class DashboardStatsSerializer(serializers.Serializer):
    """Serializes a ``DashboardStatsDTO`` into the response body."""

    range_days = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
    leads = serializers.SerializerMethodField()
    is_sampled = serializers.SerializerMethodField()
    is_partial = serializers.SerializerMethodField()

    def get_leads(self, stats):
        return DashboardLeadsSerializer(
            {
                "total": stats.total,
                "new_in_range": stats.new_in_range,
                "new_previous_range": stats.new_previous_range,
                "converted": stats.converted,
                "by_status": [{"status": v, "count": c} for v, c in stats.by_status],
                "by_source": [{"source": v, "count": c} for v, c in stats.by_source],
                "created_per_day": [{"date": d, "count": c} for d, c in stats.created_per_day],
            }
        ).data

    # Computed exactly in the database, never sampled or partial.
    def get_is_sampled(self, stats):
        return False

    def get_is_partial(self, stats):
        return False
