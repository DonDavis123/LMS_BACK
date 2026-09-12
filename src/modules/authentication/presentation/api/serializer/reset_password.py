from rest_framework import serializers


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(
        trim_whitespace=False,
    )

    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )