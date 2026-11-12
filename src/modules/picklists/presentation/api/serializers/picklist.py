from rest_framework import serializers


class PicklistOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    value = serializers.CharField()
    sort_order = serializers.IntegerField()
    is_active = serializers.BooleanField()
    is_system = serializers.BooleanField()
    # Palette key, or "" when no colour has been chosen.
    color = serializers.CharField(allow_blank=True)
    # Present only in the admin view (include_inactive=true).
    usage_count = serializers.IntegerField(allow_null=True)


class PicklistFieldSerializer(serializers.Serializer):
    module = serializers.CharField()
    field = serializers.CharField()
    label = serializers.CharField()
    options = PicklistOptionSerializer(many=True)


class CreatePicklistOptionSerializer(serializers.Serializer):
    # Length/whitespace rules live in the domain (they differ per field).
    value = serializers.CharField(trim_whitespace=False)
    # Palette key; whether it is a known colour is checked in the domain.
    color = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class UpdatePicklistOptionSerializer(serializers.Serializer):
    value = serializers.CharField(required=False, trim_whitespace=False)
    is_active = serializers.BooleanField(required=False)
    color = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide a new value, color and/or is_active."
            )
        return attrs


class ReorderPicklistOptionsSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )
