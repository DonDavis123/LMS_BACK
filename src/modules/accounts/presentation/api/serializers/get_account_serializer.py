from rest_framework import serializers


class AccountContactSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    mobile = serializers.CharField(allow_null=True)
    contact_owner_id = serializers.UUIDField()
    contact_owner_name = serializers.CharField(allow_null=True)


class AccountDetailsSerializer(serializers.Serializer):
    id = serializers.UUIDField()

    account_owner_id = serializers.UUIDField()
    account_owner_name = serializers.CharField(allow_null=True)

    account_name = serializers.CharField()
    account_site = serializers.CharField(allow_null=True)
    account_number = serializers.CharField(allow_null=True)
    account_type = serializers.CharField(allow_null=True)
    industry = serializers.CharField(allow_null=True)
    annual_revenue = serializers.IntegerField(allow_null=True)
    rating = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    website = serializers.CharField(allow_null=True)
    ticker_symbol = serializers.CharField(allow_null=True)
    ownership = serializers.CharField()
    employees = serializers.IntegerField(allow_null=True)
    sic_code = serializers.CharField(allow_null=True)

    billing_address = serializers.CharField(allow_null=True)
    billing_city = serializers.CharField(allow_null=True)
    billing_state = serializers.CharField(allow_null=True)
    billing_country = serializers.CharField(allow_null=True)
    billing_postal_code = serializers.CharField(allow_null=True)

    description = serializers.CharField(allow_null=True)

    created_by_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()

    modified_by_id = serializers.UUIDField()
    updated_at = serializers.DateTimeField()

    contacts = AccountContactSerializer(many=True)
