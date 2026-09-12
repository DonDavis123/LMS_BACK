from rest_framework import serializers


class UpdateAccountSerializer(serializers.Serializer):
    account_name = serializers.CharField(
        max_length=255,
    )

    account_site = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    account_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    account_type = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    industry = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    annual_revenue = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    rating = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    website = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    ticker_symbol = serializers.CharField(
        max_length=50,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    ownership = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    employees = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    sic_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    billing_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    billing_city = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    billing_state = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    billing_country = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    billing_postal_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )