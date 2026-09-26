from rest_framework import serializers

from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus


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

    lead_source = serializers.ChoiceField(
        choices=[
            (source.value, source.value)
            for source in LeadSource
        ],
        required=False,
    )

    lead_status = serializers.ChoiceField(
        choices=[
            (status.value, status.value)
            for status in LeadStatus
        ],
        required=False,
    )

    industry = serializers.ChoiceField(
        choices=[
            (industry.value, industry.value)
            for industry in LeadIndustry
        ],
        required=False,
    )

    rating = serializers.ChoiceField(
        choices=[
            (rating.value, rating.value)
            for rating in LeadRating
        ],
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