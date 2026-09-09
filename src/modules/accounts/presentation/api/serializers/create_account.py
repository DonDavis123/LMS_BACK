from rest_framework import serializers


class CreateAccountSerializer(serializers.Serializer):
    account_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    account_name = serializers.CharField(
        max_length=255,
    )

    account_site = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    account_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    account_type = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    industry = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    annual_revenue = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    rating = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    website = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    ticker_symbol = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    ownership = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    employees = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    sic_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )