from rest_framework import serializers

from src.modules.shared.presentation.password_validation import password_errors


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(
        trim_whitespace=False,
    )

    new_password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )

    def validate_new_password(self, value):
        # Length, common / numeric-only passwords (Django's validators). The
        # similarity check is skipped: the account is only known from the
        # token, which the use case consumes.
        errors = password_errors(value)
        if errors:
            raise serializers.ValidationError(errors)
        return value
