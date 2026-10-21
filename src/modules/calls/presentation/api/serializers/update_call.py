from collections.abc import Mapping

from rest_framework import serializers

from src.modules.calls.domain.entities.call import (
    MAX_DESCRIPTION_LENGTH,
    MAX_DURATION_SECONDS,
)
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType


class UpdateCallSerializer(serializers.Serializer):
    """Only the editable call fields are accepted.

    Immutable fields (lead_id, contact_id, account_id, owner_id,
    entry_method) and any other unknown field are rejected with a 400
    instead of being silently ignored.
    """

    call_start_time = serializers.DateTimeField(required=False)
    duration_seconds = serializers.IntegerField(
        min_value=0,
        max_value=MAX_DURATION_SECONDS,
        required=False,
    )
    call_type = serializers.ChoiceField(
        choices=[
            (call_type.value, call_type.value)
            for call_type in CallType
        ],
        required=False,
    )
    outcome = serializers.ChoiceField(
        choices=[
            (outcome.value, outcome.value)
            for outcome in CallOutcome
        ],
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=MAX_DESCRIPTION_LENGTH,
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            rejected = sorted(set(data) - set(self.fields))

            if rejected:
                raise serializers.ValidationError({
                    field: "This field cannot be updated."
                    for field in rejected
                })

        return super().to_internal_value(data)
