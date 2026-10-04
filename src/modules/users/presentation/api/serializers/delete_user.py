from collections.abc import Mapping

from rest_framework import serializers


class DeleteUserSerializer(serializers.Serializer):
    # Presence/ownership rules are business validation and live in the
    # Application use case; this only checks the HTTP payload shape.
    replacement_user_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError(
                {"non_field_errors": ["Request body must be an object."]}
            )

        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError({
                field: "This field is not allowed."
                for field in sorted(unknown_fields)
            })

        return super().to_internal_value(data)
