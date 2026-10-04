from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class DeletionPreviewUserDTO:
    id: UUID
    name: str
    email: str


@dataclass(frozen=True)
class DeletionImpactDTO:
    leads: int
    contacts: int
    accounts: int
    tasks: int
    meetings: int
    reminders: int
    notifications: int
    timeline: int


@dataclass(frozen=True)
class TransferRequiredDTO:
    leads: bool
    contacts: bool
    accounts: bool
    meetings: bool


@dataclass(frozen=True)
class PermanentDeletionsDTO:
    tasks: int
    reminders: int
    notifications: int


@dataclass(frozen=True)
class UserActionDTO:
    type: str


@dataclass(frozen=True)
class UserDeletionPreviewDTO:
    user: DeletionPreviewUserDTO
    impact: DeletionImpactDTO
    transfer_required: TransferRequiredDTO
    permanent_deletions: PermanentDeletionsDTO
    user_action: UserActionDTO
    can_retire: bool
    blockers: tuple[str, ...] = field(default_factory=tuple)
    has_related_data: bool = False
    user_is_blocked: bool = False
    available_actions: tuple[str, ...] = field(default_factory=tuple)
