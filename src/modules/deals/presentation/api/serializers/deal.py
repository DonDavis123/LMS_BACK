from rest_framework import serializers


class DealSerializer(serializers.Serializer):
    """Flat serializer of a domain Deal (create / update / move responses)."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    expected_close_date = serializers.DateField(allow_null=True)
    stage = serializers.CharField(source="stage.value")
    probability = serializers.IntegerField()
    owner_id = serializers.UUIDField()
    account_id = serializers.UUIDField(allow_null=True)
    contact_id = serializers.UUIDField(allow_null=True)
    source_lead_id = serializers.UUIDField(allow_null=True)
    lead_source = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    lost_reason = serializers.CharField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    created_by_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
