from rest_framework import serializers

from src.modules.shared.presentation.serializer_fields import (
    EmailAddressField,
    PhoneNumberField,
)


class UpdateContactSerializer(serializers.Serializer):
    account_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    contact_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    name = serializers.CharField(
        max_length=255,
        required=False,
    )

    email = EmailAddressField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    secondary_email = EmailAddressField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    phone = PhoneNumberField(
        required=False,
    )

    other_phone = PhoneNumberField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    mobile = PhoneNumberField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    home_phone = PhoneNumberField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    assistant_phone = PhoneNumberField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    title = serializers.CharField(
        max_length=150,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    department = serializers.CharField(
        max_length=150,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    lead_source = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    vendor_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
    )

    assistant = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    email_opt_out = serializers.BooleanField(
        required=False,
    )

    reporting_to_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    mailing_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    mailing_city = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    mailing_state = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    mailing_country = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    mailing_postal_code = serializers.CharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    other_address = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )