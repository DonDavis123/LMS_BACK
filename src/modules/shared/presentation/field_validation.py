from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.application.services.contact_field_rules import (
    PHONE_REQUIRED_MESSAGE,
    email_error,
    phone_error,
)
from src.modules.shared.application.dto.contact_point_match import (
    RECORD_ACCOUNT,
    RECORD_CONTACT,
    RECORD_LEAD,
)
from src.modules.shared.application.services.duplicate_guard import DuplicateGuard
from src.modules.shared.infrastructure.persistence.django_contact_point_directory import (
    DjangoContactPointDirectory,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class FieldValidationRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(choices=["phone", "email"])
    value = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    required = serializers.BooleanField(required=False, default=False)
    # The record being edited, so it is not reported as its own duplicate.
    exclude_type = serializers.ChoiceField(
        choices=[RECORD_LEAD, RECORD_CONTACT, RECORD_ACCOUNT],
        required=False,
        allow_null=True,
    )
    exclude_id = serializers.UUIDField(required=False, allow_null=True)


class ValidateFieldView(APIView):
    """Stateless format check used by forms while the user is typing.

    Checks the format and, when the format is fine, whether another lead,
    contact or account already uses the value. Always answers 200 with
    ``{"valid": bool, "message": str | null, "duplicate": null | {...}}`` so
    the form can show the message under the field without handling errors.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request):
        serializer = FieldValidationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        value = (data.get("value") or "").strip()
        required = data["required"]

        message = None
        if not value:
            if required:
                message = (
                    PHONE_REQUIRED_MESSAGE
                    if data["field"] == "phone"
                    else "Email is required."
                )
        elif data["field"] == "phone":
            message = phone_error(value)
        else:
            message = email_error(value)

        duplicate = None
        if message is None and value:
            exclude = None
            if data.get("exclude_type") and data.get("exclude_id"):
                exclude = (data["exclude_type"], data["exclude_id"])
            ctx = get_tenant_context(request)
            guard = DuplicateGuard(
                DjangoContactPointDirectory(company_id=ctx.company_id)
            )
            key = "emails" if data["field"] == "email" else "phones"
            matches = guard.find(**{key: [value]}, exclude=exclude)
            if matches:
                first = matches[0]
                label = "email address" if data["field"] == "email" else "phone number"
                message = (
                    f'This {label} is already used by the '
                    f'{first.record_type} "{first.record_name}".'
                )
                duplicate = {
                    "record_type": first.record_type,
                    "record_id": str(first.record_id),
                    "record_name": first.record_name,
                }

        return Response(
            {"valid": message is None, "message": message, "duplicate": duplicate}
        )
