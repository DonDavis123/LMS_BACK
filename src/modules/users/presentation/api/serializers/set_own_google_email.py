from collections.abc import Mapping

from rest_framework import serializers


class SetOwnGoogleEmailSerializer(serializers.Serializer):
    # Format is validated by the use case so that an invalid address
    # returns {"detail": "..."} like the other business errors.
    google_email = serializers.CharField(
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
        max_length=254,
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
