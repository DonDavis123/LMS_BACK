from rest_framework import serializers

from src.modules.calls.domain.entities.call import (
    MAX_DESCRIPTION_LENGTH,
    MAX_DURATION_SECONDS,
)
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType


class CreateCallSerializer(serializers.Serializer):
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    contact_id = serializers.UUIDField(required=False, allow_null=True)
    account_id = serializers.UUIDField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    call_type = serializers.ChoiceField(
        choices=[
            (call_type.value, call_type.value)
            for call_type in CallType
        ],
        required=False,
        default=CallType.OUTBOUND.value,
    )
    outcome = serializers.ChoiceField(
        choices=[
            (outcome.value, outcome.value)
            for outcome in CallOutcome
        ],
    )
    call_start_time = serializers.DateTimeField()
    duration_seconds = serializers.IntegerField(
        min_value=0,
        max_value=MAX_DURATION_SECONDS,
        required=False,
        default=0,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    entry_method = serializers.ChoiceField(
        choices=[
            (method.value, method.value)
            for method in CallEntryMethod
        ],
        required=False,
        default=CallEntryMethod.MANUAL.value,
    )
