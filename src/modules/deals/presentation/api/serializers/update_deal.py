from rest_framework import serializers

from src.modules.deals.domain.enums.deal_stage import DealStage


class UpdateDealSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
    )
    expected_close_date = serializers.DateField(required=False, allow_null=True)
    stage = serializers.ChoiceField(
        choices=[(stage.value, stage.value) for stage in DealStage],
        required=False,
    )
    probability = serializers.IntegerField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False)
    account_id = serializers.UUIDField(required=False, allow_null=True)
    contact_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    lost_reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
