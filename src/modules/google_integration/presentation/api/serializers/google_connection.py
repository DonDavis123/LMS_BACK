from rest_framework import serializers


class GoogleConnectionStatusSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    connected = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    google_email = serializers.CharField(allow_null=True)
    connected_at = serializers.DateTimeField(allow_null=True)
