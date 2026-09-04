from rest_framework import serializers

from src.modules.users.domain.entities.role import UserRole


class CreateUserSerializer(serializers.Serializer):

    name = serializers.CharField(
        max_length=150,
    )

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    role = serializers.ChoiceField(
        choices=[
            (role.value, role.name)
            for role in UserRole
        ],
    )