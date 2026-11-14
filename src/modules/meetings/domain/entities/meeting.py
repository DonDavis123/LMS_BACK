from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus


@dataclass
class Meeting:
    id: UUID
    title: str
    description: str | None
    location: str | None
    is_all_day: bool
    start_at: datetime
    end_at: datetime
    reminder_at: datetime | None
    host_id: UUID
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    # Video conference (Google Meet). All optional so plain meetings are unchanged.
    meet_link: str | None = None
    external_event_id: str | None = None
    conference_provider: ConferenceProvider | None = None
    conference_status: ConferenceStatus = ConferenceStatus.NONE
    conference_error: str | None = None
    # User whose calendar holds the external event.
    calendar_owner_id: UUID | None = None

    @classmethod
    def create(
        cls,
        title: str,
        start_at: datetime,
        end_at: datetime,
        host_id: UUID,
        created_by_id: UUID,
        description: str | None = None,
        location: str | None = None,
        is_all_day: bool = False,
        reminder_at: datetime | None = None,
    ) -> "Meeting":
        if not title or not title.strip():
            raise ValueError("Meeting title cannot be empty.")

        if end_at < start_at:
            raise ValueError("Meeting end time cannot be earlier than start time.")

        if not host_id:
            raise ValueError("Meeting host is required.")

        if not created_by_id:
            raise ValueError("Meeting creator is required.")

        if reminder_at is not None and not isinstance(reminder_at, datetime):
            raise ValueError("Meeting reminder time must be a datetime.")

        now = datetime.now(timezone.utc)

        return cls(
            id=uuid4(),
            title=title,
            description=description,
            location=location,
            is_all_day=is_all_day,
            start_at=start_at,
            end_at=end_at,
            reminder_at=reminder_at,
            host_id=host_id,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Meeting is already deleted.")

        self.is_deleted = True

    @property
    def has_conference(self) -> bool:
        return bool(self.external_event_id) and self.conference_status == ConferenceStatus.CREATED

    def mark_conference_created(
        self,
        provider: ConferenceProvider,
        external_event_id: str,
        meet_link: str,
        calendar_owner_id: UUID,
    ) -> None:
        self.conference_provider = provider
        self.external_event_id = external_event_id
        self.meet_link = meet_link
        self.calendar_owner_id = calendar_owner_id
        self.conference_status = ConferenceStatus.CREATED
        self.conference_error = None

    def mark_conference_failed(self, provider: ConferenceProvider, error: str) -> None:
        self.conference_provider = provider
        self.conference_status = ConferenceStatus.FAILED
        self.conference_error = (error or "Google Meet could not be created.")[:1000]
