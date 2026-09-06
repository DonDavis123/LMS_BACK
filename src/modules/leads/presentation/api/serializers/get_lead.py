from rest_framework import serializers


class OwnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class LeadSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    company_name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    mobile_number = serializers.CharField()
    lead_source = serializers.CharField()
    owner = OwnerSerializer()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()