from rest_framework import serializers

from src.modules.shared.application.services.contact_field_rules import (
    EMAIL_MAX_LENGTH,
    PHONE_MAX_LENGTH,
    PHONE_REQUIRED_MESSAGE,
    email_error,
    phone_error,
)


def _validate_phone(value):
    message = phone_error(value)
    if message:
        raise serializers.ValidationError(message)


def _validate_email(value):
    message = email_error(value)
    if message:
        raise serializers.ValidationError(message)


class PhoneNumberField(serializers.CharField):
    """Phone field with format checks.

    Defaults to required and non-blank. Optional phones pass
    ``required=False, allow_blank=True, allow_null=True``. On update
    serializers a required phone uses ``required=False`` only, so it may be
    left out of the request but cannot be sent empty.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", PHONE_MAX_LENGTH)
        errors = dict(kwargs.pop("error_messages", {}))
        errors.setdefault("required", PHONE_REQUIRED_MESSAGE)
        errors.setdefault("blank", PHONE_REQUIRED_MESSAGE)
        errors.setdefault("null", PHONE_REQUIRED_MESSAGE)
        super().__init__(error_messages=errors, **kwargs)
        self.validators.append(_validate_phone)


class EmailAddressField(serializers.EmailField):
    """Email field with a stricter format check than Django's default."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", EMAIL_MAX_LENGTH)
        super().__init__(**kwargs)
        self.validators.append(_validate_email)
