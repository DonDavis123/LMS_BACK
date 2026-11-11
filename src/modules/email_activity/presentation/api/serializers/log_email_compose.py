from uuid import UUID

from rest_framework import serializers

from src.modules.email_activity.application.dto.log_email_compose import ComposeTarget
from src.modules.email_activity.domain.enums.channel import EmailChannel
from src.modules.email_activity.domain.enums.record_type import RecordType

_CHANNEL_VALUES = [channel.value for channel in EmailChannel]
_RECORD_TYPE_VALUES = [record_type.value for record_type in RecordType]


class LogEmailComposeRequestSerializer(serializers.Serializer):
    """Shape of the body of ``POST /api/email-activity/compose/``.

    Only the types are checked here. The limits (1..50 targets, subject
    length, batch rules) belong to the use case.
    ``validated_data["targets"]`` is a tuple of ``ComposeTarget``.
    """

    # A CharField, not a UUIDField: DRF's UUIDField also accepts bare integers.
    client_ref = serializers.CharField(
        error_messages={"invalid": "client_ref must be a valid UUID."},
    )
    channel = serializers.ChoiceField(
        choices=_CHANNEL_VALUES,
        error_messages={
            "invalid_choice": "channel must be one of: " + ", ".join(_CHANNEL_VALUES) + ".",
        },
    )
    targets = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True,
        error_messages={"not_a_list": "targets must be a list."},
    )
    subject = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        error_messages={"invalid": "subject must be a string."},
    )
    batch_index = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "batch_index must be a whole number."},
    )
    batch_total = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "batch_total must be a whole number."},
    )

    def validate_client_ref(self, value):
        try:
            return UUID(value)
        except ValueError:
            raise serializers.ValidationError("client_ref must be a valid UUID.")

    def validate_channel(self, value):
        return EmailChannel(value)

    def validate_targets(self, value):
        parsed = []
        for index, item in enumerate(value):
            record_type = item.get("record_type")
            if record_type not in _RECORD_TYPE_VALUES:
                raise serializers.ValidationError(
                    f"targets[{index}].record_type must be one of: "
                    + ", ".join(_RECORD_TYPE_VALUES)
                    + "."
                )
            try:
                if not isinstance(item.get("record_id"), str):
                    raise ValueError
                record_id = UUID(item["record_id"])
            except ValueError:
                raise serializers.ValidationError(
                    f"targets[{index}].record_id must be a valid UUID."
                )
            parsed.append(ComposeTarget(RecordType(record_type), record_id))
        return tuple(parsed)


class ComposeTargetSerializer(serializers.Serializer):
    record_type = serializers.CharField(source="record_type.value")
    record_id = serializers.UUIDField()


class LogEmailComposeResponseSerializer(serializers.Serializer):
    logged = serializers.IntegerField()
    already_logged = serializers.IntegerField()
    not_found = ComposeTargetSerializer(many=True)


def _first_message(messages) -> str:
    if isinstance(messages, dict):
        messages = list(messages.values())
    if isinstance(messages, (list, tuple)):
        return _first_message(messages[0]) if messages else "Invalid request."
    return str(messages)


def validation_detail(errors) -> str:
    """One readable message out of DRF's error dict (first error wins)."""
    if isinstance(errors, dict):
        for key, messages in errors.items():
            text = _first_message(messages)
            if key == "non_field_errors" or text.startswith(key):
                return text
            return f"{key}: {text}"
    if isinstance(errors, (list, tuple)) and errors:
        return _first_message(errors)
    return "Invalid request."
