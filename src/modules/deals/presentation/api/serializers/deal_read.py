from rest_framework import serializers


class DealReadSerializer(serializers.Serializer):
    """Serializer for deal read endpoints (list and detail).

    Relationship IDs are kept and the display names are added so clients do
    not have to render UUIDs. Decimal fields are serialized as strings.
    """

    id = serializers.UUIDField(source="deal.id")
    name = serializers.CharField(source="deal.name")
    amount = serializers.DecimalField(
        source="deal.amount", max_digits=14, decimal_places=2
    )
    expected_close_date = serializers.DateField(
        source="deal.expected_close_date", allow_null=True
    )
    stage = serializers.CharField(source="deal.stage.value")
    probability = serializers.IntegerField(source="deal.probability")

    owner_id = serializers.UUIDField(source="deal.owner_id")
    owner_name = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(source="deal.account_id", allow_null=True)
    account_name = serializers.CharField(allow_null=True)

    contact_id = serializers.UUIDField(source="deal.contact_id", allow_null=True)
    contact_name = serializers.CharField(allow_null=True)

    source_lead_id = serializers.UUIDField(
        source="deal.source_lead_id", allow_null=True
    )
    source_lead_name = serializers.CharField(allow_null=True)

    lead_source = serializers.CharField(source="deal.lead_source", allow_null=True)
    description = serializers.CharField(source="deal.description", allow_null=True)
    lost_reason = serializers.CharField(source="deal.lost_reason", allow_null=True)
    closed_at = serializers.DateTimeField(source="deal.closed_at", allow_null=True)
    created_by_id = serializers.UUIDField(source="deal.created_by_id")
    created_at = serializers.DateTimeField(source="deal.created_at")
    updated_at = serializers.DateTimeField(source="deal.updated_at")
