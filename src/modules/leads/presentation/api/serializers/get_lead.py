from rest_framework import serializers


class LeadSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    lead_generator = serializers.CharField()
    client_partner_name = serializers.CharField()
    mobile_number = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    city_location = serializers.CharField(allow_null=True)
    business_type = serializers.CharField()
    lead_source = serializers.CharField()
    remarks = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()