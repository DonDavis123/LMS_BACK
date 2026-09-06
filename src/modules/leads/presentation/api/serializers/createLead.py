from rest_framework import serializers

from src.modules.leads.domain.entities.lead_source import LeadSource


class CreateLeadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)

    company_name = serializers.CharField(max_length=255)

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    mobile_number = serializers.CharField(max_length=20)

    lead_source = serializers.ChoiceField(
        choices=[
            (source.value, source.value)
            for source in LeadSource
        ]
    )