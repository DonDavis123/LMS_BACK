from rest_framework import serializers


class OwnerDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class LeadDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()

    name = serializers.CharField()
    title = serializers.CharField(
        allow_null=True,
    )

    company_name = serializers.CharField(allow_null=True, allow_blank=True)

    email = serializers.EmailField(
        allow_null=True,
    )

    mobile_number = serializers.CharField()

    phone = serializers.CharField(
        allow_null=True,
    )

    lead_source = serializers.CharField()
    lead_status = serializers.CharField()
    industry = serializers.CharField()
    rating = serializers.CharField()

    website = serializers.URLField(
        allow_null=True,
    )

    number_of_employees = serializers.IntegerField(
        allow_null=True,
    )

    annual_revenue = serializers.IntegerField(
        allow_null=True,
    )

    owner = OwnerDetailSerializer()

    address = serializers.CharField(
        allow_null=True,
    )

    city = serializers.CharField(
        allow_null=True,
    )

    state = serializers.CharField(
        allow_null=True,
    )

    country = serializers.CharField(
        allow_null=True,
    )

    postal_code = serializers.CharField(
        allow_null=True,
    )

    description = serializers.CharField(
        allow_null=True,
    )

    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()