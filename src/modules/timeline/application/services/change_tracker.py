from datetime import date, datetime
from enum import Enum
from uuid import UUID


def serialize_change_value(value: object) -> object:
    """Convert domain values into JSON-safe Timeline metadata values."""
    if isinstance(value, Enum):
        return serialize_change_value(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def build_field_changes(old_values: dict[str, object], new_values: dict[str, object]) -> dict:
    """Return only fields whose serialized values actually changed."""
    changes: dict[str, dict[str, object]] = {}

    for field, old_value in old_values.items():
        if field not in new_values:
            continue

        old_serialized = serialize_change_value(old_value)
        new_serialized = serialize_change_value(new_values[field])

        if old_serialized != new_serialized:
            changes[field] = {
                "old_value": old_serialized,
                "new_value": new_serialized,
            }

    return changes
