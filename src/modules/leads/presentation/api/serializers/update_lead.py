from rest_framework import serializers



class UpdateLeadSerializer(serializers.Serializer):

    name = serializers.CharField(
        max_length=255,
        required=False,
    )

    title = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    company_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mobile_number = serializers.CharField(
        max_length=20,
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

    # Allowed values are the company's own options (editable by its
    # superadmins), so they are checked per company in the use case rather
    # than against a fixed list here.
    lead_source = serializers.CharField(
        max_length=100,
        required=False,
    )

    lead_status = serializers.CharField(
        max_length=100,
        required=False,
    )

    industry = serializers.CharField(
        max_length=150,
        required=False,
    )

    rating = serializers.CharField(
        max_length=100,
        required=False,
    )

    website = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    number_of_employees = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    annual_revenue = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    # Owner can be changed during update
    owner_id = serializers.UUIDField(
        required=False,
    )

    address = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    city = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    state = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    country = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    postal_code = serializers.CharField(
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