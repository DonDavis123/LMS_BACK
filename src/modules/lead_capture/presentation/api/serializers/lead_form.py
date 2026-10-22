from django.conf import settings
from rest_framework import serializers

from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode


def build_public_url(public_token: str) -> str:
    """``{FRONTEND_URL}/lead/{token}``. The QR image is drawn by the client."""
    base = (getattr(settings, "FRONTEND_URL", None) or "").rstrip("/")
    return f"{base}/lead/{public_token}"


class FormOwnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class RotationOwnerSerializer(FormOwnerSerializer):
    position = serializers.IntegerField()


class LeadFormSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    lead_source = serializers.CharField(allow_null=True)
    assignment_mode = serializers.CharField()
    single_owner = FormOwnerSerializer(allow_null=True)
    rotation_owners = RotationOwnerSerializer(many=True)
    is_active = serializers.BooleanField()
    is_configured = serializers.BooleanField()
    needs_attention = serializers.BooleanField()
    public_token = serializers.CharField()
    public_url = serializers.SerializerMethodField()
    submission_count = serializers.IntegerField()
    last_submission_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_public_url(self, form) -> str:
        return build_public_url(form.public_token)


class UpdateLeadFormSerializer(serializers.Serializer):
    # Length/whitespace rules live in the use case.
    title = serializers.CharField(required=False, trim_whitespace=False)
    lead_source = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, trim_whitespace=False
    )
    assignment_mode = serializers.ChoiceField(
        required=False, choices=[mode.value for mode in AssignmentMode]
    )
    single_owner_id = serializers.UUIDField(required=False, allow_null=True)
    rotation_owner_ids = serializers.ListField(
        required=False,
        child=serializers.UUIDField(),
        allow_empty=False,
    )

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                {name: ["Unknown field."] for name in unknown}
            )
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs
