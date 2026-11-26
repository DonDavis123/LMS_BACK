from rest_framework import serializers

from src.modules.shared.presentation.password_validation import password_errors
from src.modules.users.domain.entities.role import MANAGEABLE_ROLES


class CreateUserSerializer(serializers.Serializer):

    name = serializers.CharField(
        max_length=150,
    )

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,
    )

    role = serializers.ChoiceField(
        choices=[
            (role.value, role.name)
            for role in MANAGEABLE_ROLES
        ],
    )

    def validate(self, attrs):
        errors = password_errors(
            attrs["password"],
            email=attrs.get("email"),
            name=attrs.get("name"),
        )
        if errors:
            raise serializers.ValidationError({"password": errors})
        return attrs
