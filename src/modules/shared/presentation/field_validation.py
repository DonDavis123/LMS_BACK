from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.application.services.contact_field_rules import (
    PHONE_REQUIRED_MESSAGE,
    email_error,
    phone_error,
)
from src.modules.shared.presentation.permissions import IsCompanyUser


class FieldValidationRequestSerializer(serializers.Serializer):
    field = serializers.ChoiceField(choices=["phone", "email"])
    value = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    required = serializers.BooleanField(required=False, default=False)


class ValidateFieldView(APIView):
    """Stateless format check used by forms while the user is typing.

    Always answers 200 with ``{"valid": bool, "message": str | null}`` so the
    form can show the message under the field without handling errors.
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

        return Response({"valid": message is None, "message": message})
