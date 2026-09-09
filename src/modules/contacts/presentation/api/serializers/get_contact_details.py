from rest_framework import serializers


class ContactDetailsSerializer(serializers.Serializer):
    id = serializers.UUIDField()

    name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    secondary_email = serializers.EmailField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    other_phone = serializers.CharField(allow_null=True)
    mobile = serializers.CharField(allow_null=True)
    home_phone = serializers.CharField(allow_null=True)
    assistant_phone = serializers.CharField(allow_null=True)

    title = serializers.CharField(allow_null=True)
    department = serializers.CharField(allow_null=True)
    lead_source = serializers.CharField(allow_null=True)
    vendor_name = serializers.CharField(allow_null=True)

    date_of_birth = serializers.DateField(allow_null=True)
    assistant = serializers.CharField(allow_null=True)
    email_opt_out = serializers.BooleanField()

    reporting_to_id = serializers.UUIDField(allow_null=True)

    mailing_address = serializers.CharField(allow_null=True)
    mailing_city = serializers.CharField(allow_null=True)
    mailing_state = serializers.CharField(allow_null=True)
    mailing_country = serializers.CharField(allow_null=True)
    mailing_postal_code = serializers.CharField(allow_null=True)
    other_address = serializers.CharField(allow_null=True)

    description = serializers.CharField(allow_null=True)

    account_id = serializers.UUIDField(allow_null=True)
    account_name = serializers.CharField(allow_null=True)

    contact_owner_id = serializers.UUIDField()
    contact_owner_name = serializers.CharField(allow_null=True)

    created_by_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()

    modified_by_id = serializers.UUIDField()
    updated_at = serializers.DateTimeField()