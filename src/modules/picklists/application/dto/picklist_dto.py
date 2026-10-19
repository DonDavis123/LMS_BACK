from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PicklistOptionDTO:
    id: UUID
    value: str
    sort_order: int
    is_active: bool
    is_system: bool
    # Only filled in for the admin (include_inactive) view.
    usage_count: int | None = None


@dataclass(frozen=True)
class PicklistFieldDTO:
    module: str
    field: str
    label: str
    options: list[PicklistOptionDTO]
