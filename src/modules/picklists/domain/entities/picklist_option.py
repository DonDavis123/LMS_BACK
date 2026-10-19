from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .picklist_catalog import PicklistField


def normalize_option_value(raw: object, definition: PicklistField) -> str:
    """Validate and clean text typed by an admin for an option."""
    if not isinstance(raw, str):
        raise ValueError("Option value must be text.")

    # Collapse runs of whitespace so "Trade   Show" and "Trade Show" match.
    value = " ".join(raw.split())

    if not value:
        raise ValueError("Option value cannot be empty.")
    if len(value) > definition.max_length:
        raise ValueError(
            f"Option value cannot be longer than {definition.max_length} characters."
        )
    if any(ord(char) < 32 for char in value):
        raise ValueError("Option value contains invalid characters.")

    return value


@dataclass
class PicklistOption:
    id: UUID
    module: str
    field: str
    value: str
    sort_order: int
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        module: str,
        field: str,
        value: str,
        sort_order: int,
        is_system: bool = False,
    ) -> "PicklistOption":
        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            module=module,
            field=field,
            value=value,
            sort_order=sort_order,
            is_active=True,
            is_system=is_system,
            created_at=now,
            updated_at=now,
        )

    def _ensure_editable(self) -> None:
        if self.is_system:
            raise ValueError(
                f'The "{self.value}" option is built in and cannot be changed.'
            )

    def rename(self, new_value: str) -> None:
        self._ensure_editable()
        self.value = new_value

    def deactivate(self) -> None:
        self._ensure_editable()
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def ensure_deletable(self) -> None:
        self._ensure_editable()
