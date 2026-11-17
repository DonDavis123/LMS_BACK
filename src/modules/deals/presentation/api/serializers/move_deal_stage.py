from rest_framework import serializers

from src.modules.deals.domain.enums.deal_stage import DealStage


class MoveDealStageSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(
        choices=[(stage.value, stage.value) for stage in DealStage],
    )
    probability = serializers.IntegerField(required=False, allow_null=True)
    lost_reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
