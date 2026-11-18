from rest_framework import serializers

# Sums over many deals can exceed a single deal's 14 digits.
MONEY_DIGITS = 20


class DealBoardQuerySerializer(serializers.Serializer):
    owner_id = serializers.UUIDField(required=False)
    expected_close_from = serializers.DateField(required=False)
    expected_close_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    # Range and the from/to order are checked by the use case.
    closed_within_days = serializers.IntegerField(required=False, default=30)


class DealCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=MONEY_DIGITS, decimal_places=2)
    expected_close_date = serializers.DateField(allow_null=True)
    probability = serializers.IntegerField()

    owner_id = serializers.UUIDField()
    owner_name = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(allow_null=True)
    account_name = serializers.CharField(allow_null=True)

    contact_id = serializers.UUIDField(allow_null=True)
    contact_name = serializers.CharField(allow_null=True)


class DealBoardColumnSerializer(serializers.Serializer):
    stage = serializers.CharField(source="stage.value")
    default_probability = serializers.IntegerField()
    count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=MONEY_DIGITS, decimal_places=2)
    weighted_amount = serializers.DecimalField(
        max_digits=MONEY_DIGITS, decimal_places=2
    )
    has_more = serializers.BooleanField()
    deals = DealCardSerializer(many=True)


class DealBoardSerializer(serializers.Serializer):
    stages = DealBoardColumnSerializer(many=True)
