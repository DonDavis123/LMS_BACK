from django.conf import settings
from rest_framework import serializers

from .deal_board import MONEY_DIGITS


class DealForecastQuerySerializer(serializers.Serializer):
    # Same handling as the dashboard: IANA zone, default the project's
    # TIME_ZONE. An unknown zone is rejected by the use case.
    tz = serializers.CharField(
        required=False, default=settings.TIME_ZONE, max_length=64
    )
    owner_id = serializers.UUIDField(required=False)


def _money():
    return serializers.DecimalField(max_digits=MONEY_DIGITS, decimal_places=2)


class StageForecastSerializer(serializers.Serializer):
    stage = serializers.CharField(source="stage.value")
    count = serializers.IntegerField()
    total_amount = _money()
    weighted_amount = _money()


class MonthForecastSerializer(serializers.Serializer):
    month = serializers.CharField(allow_null=True)
    total_amount = _money()
    weighted_amount = _money()


class DealForecastSerializer(serializers.Serializer):
    open_pipeline = _money()
    weighted_forecast = _money()
    won_this_month = _money()
    lost_this_month = _money()
    open_deal_count = serializers.IntegerField()
    by_stage = StageForecastSerializer(many=True)
    by_month = MonthForecastSerializer(many=True)
