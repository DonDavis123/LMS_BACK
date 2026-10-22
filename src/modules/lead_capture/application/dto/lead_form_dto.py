from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

_UNSET = object()


@dataclass(frozen=True)
class FormOwnerDTO:
    id: UUID
    name: str
    position: int | None = None


@dataclass(frozen=True)
class LeadFormDTO:
    id: UUID
    title: str
    lead_source: str | None
    assignment_mode: str
    single_owner: FormOwnerDTO | None
    rotation_owners: list[FormOwnerDTO]
    is_active: bool
    is_configured: bool
    needs_attention: bool
    public_token: str
    submission_count: int
    last_submission_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class UpdateLeadFormDTO:
    """Only the fields the client sent are set; the rest stay ``_UNSET``."""

    title: str | object = _UNSET
    lead_source: str | None | object = _UNSET
    assignment_mode: str | object = _UNSET
    single_owner_id: UUID | None | object = _UNSET
    rotation_owner_ids: list[UUID] | object = _UNSET
