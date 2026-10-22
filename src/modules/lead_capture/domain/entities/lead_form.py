import secrets
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from src.modules.lead_capture.domain.entities.assignment_mode import AssignmentMode

DEFAULT_FORM_TITLE = "Contact us"
TITLE_MAX_LENGTH = 150
MAX_ROTATION_OWNERS = 50

NOT_CONFIGURED_MESSAGE = (
    "Set a lead source and at least one eligible owner before unblocking the form."
)


def generate_public_token() -> str:
    """A fresh, unguessable link token (192 bits). Never derived from an id."""
    return secrets.token_urlsafe(24)


@dataclass(frozen=True)
class FormOwner:
    """A user chosen as owner of the leads this form creates."""

    id: UUID
    name: str
    # Order in the rotation; ``None`` for the single owner.
    position: int | None = None


@dataclass
class LeadForm:
    id: UUID
    company_id: UUID
    public_token: str
    title: str
    lead_source: str  # "" = not chosen yet
    assignment_mode: AssignmentMode
    single_owner: FormOwner | None
    rotation_owners: list[FormOwner]
    is_active: bool  # False = blocked
    last_assigned_position: int | None
    submission_count: int
    last_submission_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Ids that may own leads *right now* (filled in by the use case from the
    # users module's "lead owners" rule). It is not stored, so a deactivated
    # or deleted owner is noticed immediately.
    eligible_owner_ids: frozenset[UUID] = field(default_factory=frozenset)
    # Submissions accepted on ``daily_submission_date``; only meaningful while
    # that date is today (see ``has_reached_daily_cap``).
    daily_submission_count: int = 0
    daily_submission_date: date | None = None

    # ---------------------------------------------------------------- state

    @property
    def eligible_rotation_owners(self) -> list[FormOwner]:
        return [o for o in self.rotation_owners if o.id in self.eligible_owner_ids]

    @property
    def has_eligible_owner(self) -> bool:
        if self.assignment_mode is AssignmentMode.SINGLE_OWNER:
            return (
                self.single_owner is not None
                and self.single_owner.id in self.eligible_owner_ids
            )
        return bool(self.eligible_rotation_owners)

    @property
    def is_configured(self) -> bool:
        return bool(self.lead_source) and self.has_eligible_owner

    @property
    def needs_attention(self) -> bool:
        """Live (not blocked) but unable to assign an owner or source."""
        return self.is_active and not self.is_configured

    # ------------------------------------------------------------- behaviour

    def pick_owner(self) -> FormOwner | None:
        """The owner the next submitted lead goes to, or ``None``.

        SINGLE_OWNER: the configured owner, if eligible.
        ROTATION: the first eligible owner whose position is after
        ``last_assigned_position`` (in order), wrapping around to the first
        eligible one. Ineligible owners are skipped. Needs
        ``eligible_owner_ids`` to be filled in.
        """
        if self.assignment_mode is AssignmentMode.SINGLE_OWNER:
            return self.single_owner if self.has_eligible_owner else None

        eligible = sorted(
            self.eligible_rotation_owners,
            key=lambda owner: -1 if owner.position is None else owner.position,
        )
        if not eligible:
            return None
        if self.last_assigned_position is not None:
            for owner in eligible:
                if owner.position is not None and owner.position > self.last_assigned_position:
                    return owner
        return eligible[0]

    def has_reached_daily_cap(self, today: date, cap: int) -> bool:
        """True if ``cap`` submissions were already accepted on ``today``."""
        return self.daily_submission_date == today and self.daily_submission_count >= cap

    def block(self) -> None:
        self.is_active = False

    def unblock(self) -> None:
        if not self.is_configured:
            raise ValueError(NOT_CONFIGURED_MESSAGE)
        self.is_active = True

    def regenerate_token(self) -> None:
        self.public_token = generate_public_token()
