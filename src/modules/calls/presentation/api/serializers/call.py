from rest_framework import serializers


class CallSerializer(serializers.Serializer):
    """Write-response serializer built from the domain Call entity."""

    id = serializers.UUIDField()
    lead_id = serializers.UUIDField(allow_null=True)
    contact_id = serializers.UUIDField(allow_null=True)
    account_id = serializers.UUIDField(allow_null=True)
    owner_id = serializers.UUIDField()
    call_type = serializers.CharField(source="call_type.value")
    outcome = serializers.CharField(source="outcome.value")
    call_start_time = serializers.DateTimeField()
    duration_seconds = serializers.IntegerField()
    duration_label = serializers.CharField(read_only=True)
    description = serializers.CharField(allow_null=True)
    entry_method = serializers.CharField(source="entry_method.value")
    created_by_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
