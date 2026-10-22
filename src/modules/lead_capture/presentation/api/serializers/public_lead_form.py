from rest_framework import serializers


class PublicLeadSubmissionSerializer(serializers.Serializer):
    # CharField trims whitespace and rejects blanks by default. Phone is
    # capped at 20 like the leads module's own phone field.
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=20)
    description = serializers.CharField(max_length=2000)
    # Honeypot: hidden from people, filled in by bots. Accepted here so it is
    # not rejected as unknown, but never part of a real submission (the view
    # handles it before anything else).
    fax_number = serializers.CharField(
        required=False, allow_blank=True, max_length=200
    )

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                {name: ["Unknown field."] for name in unknown}
            )
        return attrs
