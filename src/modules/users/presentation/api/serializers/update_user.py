from rest_framework import serializers

from src.modules.users.domain.entities.role import UserRole


class UpdateUserSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
        required=False,
    )
    email = serializers.EmailField(
        required=False,
    )
    role = serializers.ChoiceField(
        choices=[
            (role.value, role.name)
            for role in UserRole
        ],
        required=False,
    )

    def to_internal_value(self, data):
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError({
                field: "This field is not allowed."
                for field in sorted(unknown_fields)
            })

        return super().to_internal_value(data)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field is required for update."
            )
        return attrs
