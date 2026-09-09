from rest_framework import serializers


class CreateContactSerializer(serializers.Serializer):

    account_id = serializers.UUIDField(
        allow_null=True,
        required=False,
    )

    contact_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    name = serializers.CharField(
        max_length=255,
    )

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