from datetime import date, datetime
from enum import Enum
from typing import Callable
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


def format_field_changes(
    changes: dict[str, dict[str, object]],
    field_labels: dict[str, str] | None = None,
) -> str:
    """Format structured field changes into a concise human-readable summary."""
    labels = field_labels or {}
    parts = []

    for field, change in changes.items():
        label = labels.get(field, field.replace("_", " ").title())
        old_value = change.get("old_value")
        new_value = change.get("new_value")

        old_display = "None" if old_value is None else str(old_value)
        new_display = "None" if new_value is None else str(new_value)

        parts.append(f"{label}: {old_display} → {new_display}")

    return "; ".join(parts)


def resolve_relationship_changes(
    changes: dict[str, dict[str, object]],
    resolvers: dict[str, Callable[[UUID], str | None]],
    fallback: str = "Unknown",
) -> dict[str, dict[str, object]]:
    """Resolve UUID relationship change values to human-readable names.

    ``build_field_changes`` intentionally remains responsible only for
    serialization. This helper is an application-level enrichment step that
    uses repository-backed resolver callables supplied by the use case.
    Technical/navigation IDs outside ``changes`` are left untouched.
    """
    resolved = {
        field: dict(change)
        for field, change in changes.items()
    }

    for field, resolver in resolvers.items():
        if field not in resolved:
            continue

        for key in ("old_value", "new_value"):
            value = resolved[field].get(key)
            if value is None:
                continue

            try:
                relationship_id = UUID(str(value))
            except (TypeError, ValueError):
                continue

            display_value = resolver(relationship_id)
            resolved[field][key] = display_value if display_value else fallback

    return resolved
