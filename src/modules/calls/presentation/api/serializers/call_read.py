from rest_framework import serializers


class CallReadSerializer(serializers.Serializer):
    """Serializer for call read endpoints (list rows).

    Relationship IDs are kept for navigation while display names are exposed
    so clients do not have to render UUIDs as human-readable record names.
    """

    id = serializers.UUIDField(source="call.id")

    lead_id = serializers.UUIDField(source="call.lead_id", allow_null=True)
    lead_name = serializers.CharField(allow_null=True)

    contact_id = serializers.UUIDField(source="call.contact_id", allow_null=True)
    contact_name = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(source="call.account_id", allow_null=True)
    account_name = serializers.CharField(allow_null=True)

    owner_id = serializers.UUIDField(source="call.owner_id")
    owner_name = serializers.CharField(allow_null=True)

    call_type = serializers.CharField(source="call.call_type.value")
    outcome = serializers.CharField(source="call.outcome.value")
    call_start_time = serializers.DateTimeField(source="call.call_start_time")
    duration_seconds = serializers.IntegerField(source="call.duration_seconds")
    duration_label = serializers.CharField(source="call.duration_label")
    description = serializers.CharField(source="call.description", allow_null=True)
    entry_method = serializers.CharField(source="call.entry_method.value")
    created_by_id = serializers.UUIDField(source="call.created_by_id")
    created_at = serializers.DateTimeField(source="call.created_at")
    updated_at = serializers.DateTimeField(source="call.updated_at")
