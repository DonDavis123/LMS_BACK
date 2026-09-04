from rest_framework import serializers


class UpdateLeadSerializer(serializers.Serializer):

    client_partner_name = serializers.CharField(
        max_length=255,
        required=False,
    )

    mobile_number = serializers.CharField(
        max_length=20,
        required=False,
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )

    city_location = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    business_type = serializers.ChoiceField(
        choices=[
            ("B2B", "B2B"),
            ("B2C", "B2C"),
            ("OneS Academy", "OneS Academy"),
        ],
        required=False,
    )

    lead_source = serializers.CharField(
        max_length=100,
        required=False,
    )

    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
    )