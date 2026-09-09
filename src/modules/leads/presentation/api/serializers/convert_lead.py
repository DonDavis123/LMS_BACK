from rest_framework import serializers


class ConvertAccountSerializer(serializers.Serializer):
    account_name = serializers.CharField(max_length=255)

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

    billing_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    billing_city = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    billing_state = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    billing_country = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    billing_postal_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class ConvertContactSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    secondary_email = serializers.EmailField(
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

    other_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mobile = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    home_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    assistant_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    title = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    department = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    lead_source = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    vendor_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
    )

    assistant = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    email_opt_out = serializers.BooleanField(
        required=False,
        default=False,
    )

    reporting_to_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    mailing_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mailing_city = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mailing_state = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mailing_country = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mailing_postal_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    other_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

class ConvertLeadSerializer(serializers.Serializer):
    account_action = serializers.ChoiceField(
        choices=["create_new", "use_existing"],
    )

    account_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    account = ConvertAccountSerializer(
        required=False,
        allow_null=True,
    )

    contact_action = serializers.ChoiceField(
        choices=["create_new", "use_existing"],
    )

    contact_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    contact = ConvertContactSerializer(
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        account_action = attrs.get("account_action")
        account_id = attrs.get("account_id")

        contact_action = attrs.get("contact_action")
        contact_id = attrs.get("contact_id")

        # -----------------------------------------
        # Account validation
        # -----------------------------------------

        if account_action == "use_existing":
            if account_id is None:
                raise serializers.ValidationError({
                    "account_id": "This field is required when using an existing Account."
                })

        # -----------------------------------------
        # Contact validation
        # -----------------------------------------

        if contact_action == "use_existing":
            if contact_id is None:
                raise serializers.ValidationError({
                    "contact_id": "This field is required when using an existing Contact."
                })

        return attrs