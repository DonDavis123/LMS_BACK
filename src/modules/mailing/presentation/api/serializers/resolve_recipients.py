import json
from uuid import UUID

from rest_framework import serializers

from src.modules.mailing.application.dto.limits import (
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    MAX_EXCLUDE_IDS,
    MAX_IDS,
    MIN_BATCH_SIZE,
)
from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSelection,
    FilterSpec,
    IdsSelection,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.shared.presentation.query_params import parse_list_query

_ENTITY_VALUES = [entity.value for entity in MailEntity]


def _uuid_tuple(
    value,
    name: str,
    *,
    maximum: int,
    allow_empty: bool,
    too_many: str,
) -> tuple[UUID, ...]:
    if value is None and allow_empty:
        return ()
    if not isinstance(value, list):
        raise serializers.ValidationError(f"{name} must be a list of ids.")
    if not value and not allow_empty:
        raise serializers.ValidationError(f"{name} must contain at least one id.")
    if len(value) > maximum:
        raise serializers.ValidationError(too_many)

    parsed = []
    for index, item in enumerate(value):
        try:
            if not isinstance(item, str):
                raise ValueError
            parsed.append(UUID(item))
        except ValueError:
            raise serializers.ValidationError(
                f"{name} must contain valid UUIDs (invalid value at index {index})."
            )
    return tuple(parsed)


class ResolveRecipientsRequestSerializer(serializers.Serializer):
    """Validates the body of ``POST /api/mail/recipients/resolve/``.

    The search and filters are checked by ``parse_list_query``, the very
    function the list screens use, so a filter is valid here exactly when it
    is valid there. ``validated_data["selection"]`` is an ``IdsSelection`` or
    a ``FilterSelection``.
    """

    entity = serializers.ChoiceField(
        choices=_ENTITY_VALUES,
        error_messages={
            "invalid_choice": "entity must be one of: " + ", ".join(_ENTITY_VALUES) + ".",
        },
    )
    selection = serializers.DictField(
        error_messages={"not_a_dict": "selection must be an object."},
    )
    include_secondary_email = serializers.BooleanField(required=False, default=False)
    batch_size = serializers.IntegerField(
        required=False,
        default=DEFAULT_BATCH_SIZE,
        min_value=MIN_BATCH_SIZE,
        max_value=MAX_BATCH_SIZE,
        error_messages={
            "min_value": f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}.",
            "max_value": f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}.",
            "invalid": "batch_size must be a whole number.",
        },
    )

    def validate_selection(self, value):
        mode = value.get("mode")

        if mode == "ids":
            return IdsSelection(
                ids=_uuid_tuple(
                    value.get("ids"),
                    "ids",
                    maximum=MAX_IDS,
                    allow_empty=False,
                    too_many=f"ids mode accepts at most {MAX_IDS} ids.",
                )
            )

        if mode == "filter":
            search = value.get("search")
            if search is not None and not isinstance(search, str):
                raise serializers.ValidationError("search must be a string or null.")

            raw_filters = value.get("filters")
            if raw_filters is None:
                raw_filters = []

            try:
                # Same parser, same messages as the list query string.
                query = parse_list_query(
                    {"search": search, "filters": json.dumps(raw_filters)}
                )
            except ValueError as exc:
                raise serializers.ValidationError(str(exc))

            return FilterSelection(
                search=query.search,
                filters=tuple(
                    FilterSpec(field=f.field, operator=f.operator, value=f.value)
                    for f in query.filters
                ),
                exclude_ids=_uuid_tuple(
                    value.get("exclude_ids"),
                    "exclude_ids",
                    maximum=MAX_EXCLUDE_IDS,
                    allow_empty=True,
                    too_many=f"exclude_ids accepts at most {MAX_EXCLUDE_IDS} ids.",
                ),
            )

        raise serializers.ValidationError("selection.mode must be 'ids' or 'filter'.")


_GENERIC_MESSAGES = {"This field is required.", "This field may not be null."}


def _message(key: str, text: str) -> str:
    # The selection messages already say what they are about.
    if key == "selection" and text not in _GENERIC_MESSAGES:
        return text
    if text.startswith(key):
        return text
    return f"{key}: {text}"


def validation_detail(errors) -> str:
    """One readable message out of DRF's error dict (first error wins)."""
    if isinstance(errors, dict):
        for key, messages in errors.items():
            first = (
                messages[0]
                if isinstance(messages, (list, tuple)) and messages
                else messages
            )
            if key == "non_field_errors":
                return str(first)
            return _message(key, str(first))
    if isinstance(errors, (list, tuple)) and errors:
        return str(errors[0])
    return "Invalid request."


class RecipientSerializer(serializers.Serializer):
    record_id = serializers.UUIDField()
    record_type = serializers.CharField(source="record_type.value")
    name = serializers.CharField()
    email = serializers.CharField()
    email_kind = serializers.CharField(source="email_kind.value")
    account_name = serializers.CharField(allow_null=True)
    source_account_id = serializers.UUIDField(allow_null=True)


class SkippedRecordSerializer(serializers.Serializer):
    record_id = serializers.UUIDField()
    record_type = serializers.CharField(source="record_type.value")
    name = serializers.CharField()
    reason = serializers.CharField(source="reason.value")


class ResolveRecipientsResponseSerializer(serializers.Serializer):
    entity = serializers.CharField(source="entity.value")
    summary = serializers.SerializerMethodField()
    recipients = RecipientSerializer(many=True)
    skipped = SkippedRecordSerializer(many=True)
    batches = serializers.ListField(child=serializers.ListField(child=serializers.CharField()))

    def get_summary(self, result) -> dict:
        return {
            "selected": result.selected,
            "eligible": len(result.recipients),
            "skipped": len(result.skipped),
            "batches": len(result.batches),
        }
