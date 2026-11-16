from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus

# Participants are reminded this long before the start unless a reminder time is set.
DEFAULT_REMINDER_LEAD = timedelta(minutes=15)

# Reminder choices offered on the meeting form, in minutes before the start:
# 1 day, 1 hour, 30 minutes, 15 minutes. "None" is an empty selection.
ALLOWED_REMINDER_OFFSETS = (1440, 60, 30, 15)
MAX_REMINDER_SUBJECT_LENGTH = 255


def normalize_reminder_offsets(offsets) -> list[int] | None:
    """Validate a reminder selection.

    ``None`` means "not chosen" (legacy behaviour), ``[]`` means "none" and a
    list holds the chosen offsets, largest first, without duplicates.
    """
    if offsets is None:
        return None
    try:
        values = {int(value) for value in offsets}
    except (TypeError, ValueError):
        raise ValueError("Reminder options must be whole numbers of minutes.") from None
    invalid = values - set(ALLOWED_REMINDER_OFFSETS)
    if invalid:
        raise ValueError(
            "Unsupported reminder option. Choose from: 1 day, 1 hour, 30 minutes, 15 minutes."
        )
    return sorted(values, reverse=True)


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
    # Reminder time that the participant reminder email was already sent for.
    participant_reminder_for: datetime | None = None
    # Email invitations/updates/cancellations and the reminder email before the
    # meeting. Independent of Google Meet.
    send_email_notifications: bool = False
    # Reminder choices, in minutes before the start (see ALLOWED_REMINDER_OFFSETS).
    # None = never chosen (older meetings): ``reminder_at`` or 15 minutes applies.
    # [] = the user chose "none".
    reminder_offsets: list[int] | None = None
    # Reminder times (ISO, UTC) that were already emailed. Rescheduling the
    # meeting changes the times, so the reminders fire again by themselves.
    reminders_sent_for: list[str] = field(default_factory=list)
    # Optional custom reminder email. Empty: subject = meeting title,
    # body = meeting description.
    reminder_subject: str | None = None
    reminder_message: str | None = None
    # Not persisted: recipients that could not be emailed (no usable address),
    # filled in by the notification flow so the API can report them.
    email_skipped: list = field(default_factory=list, compare=False, repr=False)

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
        send_email_notifications: bool = False,
        reminder_offsets: list[int] | None = None,
        reminder_subject: str | None = None,
        reminder_message: str | None = None,
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

        reminder_offsets = normalize_reminder_offsets(reminder_offsets)
        reminder_subject = (reminder_subject or "").strip() or None
        if reminder_subject and len(reminder_subject) > MAX_REMINDER_SUBJECT_LENGTH:
            raise ValueError("Reminder subject is too long.")
        reminder_message = (reminder_message or "").strip() or None

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
            send_email_notifications=send_email_notifications,
            reminder_offsets=reminder_offsets,
            reminder_subject=reminder_subject,
            reminder_message=reminder_message,
        )

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Meeting is already deleted.")

        self.is_deleted = True

    def participant_reminder_time(self, default_lead: timedelta) -> datetime:
        """When participants should be reminded: ``reminder_at`` if the user
        set one, otherwise ``default_lead`` before the meeting starts."""
        return self.reminder_at or (self.start_at - default_lead)

    def reminder_times(self, default_lead: timedelta) -> list[datetime]:
        """Every moment a reminder email is due, earliest first.

        Chosen offsets win. Older meetings (no choice stored) keep the single
        legacy reminder; "none" gives no reminder at all.
        """
        if self.reminder_offsets is None:
            return [self.participant_reminder_time(default_lead)]
        return sorted(
            self.start_at - timedelta(minutes=minutes) for minutes in self.reminder_offsets
        )

    def reminder_offsets_for_calendar(self, default_lead: timedelta) -> list[int]:
        """Minutes-before values to mirror into the Google Calendar event."""
        if self.reminder_offsets is None:
            minutes = int((self.start_at - self.participant_reminder_time(default_lead)).total_seconds() // 60)
            return [max(0, minutes)]
        return list(self.reminder_offsets)

    @property
    def has_conference(self) -> bool:
        return bool(self.external_event_id) and self.conference_status == ConferenceStatus.CREATED

    def mark_calendar_event_created(self, external_event_id: str, calendar_owner_id: UUID) -> None:
        """A Google Calendar event exists but without a Meet link."""
        self.external_event_id = external_event_id
        self.calendar_owner_id = calendar_owner_id
        self.conference_error = None

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
