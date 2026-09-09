from rest_framework import serializers


class AccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    account_name = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    website = serializers.CharField(allow_null=True)
    account_owner_id = serializers.UUIDField()
    account_owner_name = serializers.CharField(allow_null=True)