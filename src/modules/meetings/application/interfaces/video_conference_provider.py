from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider


class VideoConferenceError(Exception):
    """The provider could not complete the request."""


class VideoConferenceNotConnectedError(VideoConferenceError, ValueError):
    """The calendar owner has not connected (or lost) their provider account."""


@dataclass(frozen=True)
class ConferenceEvent:
    """Provider-neutral description of the calendar event behind a meeting."""

    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    attendee_emails: tuple[str, ...]
    # Stable id derived from the CRM meeting, so retrying a create whose
    # response was lost cannot produce a duplicate event.
    client_event_id: str
    # False creates a plain calendar event (no Meet link).
    with_meet: bool = True
    # Whether Google emails the attendees (invite, updates, cancellation).
    notify_attendees: bool = True
    # Minutes before the start for the organizer's Google Calendar popup and
    # email reminders. None leaves Google's defaults.
    reminder_minutes: int | None = None
    # Several reminders chosen on the meeting form (minutes before the start).
    # When not None it replaces ``reminder_minutes``; an empty tuple means the
    # organizer gets no Google reminders.
    reminder_overrides: tuple[int, ...] | None = None


@dataclass(frozen=True)
class ConferenceEventResult:
    event_id: str
    # None for a calendar event created without Meet.
    meet_link: str | None


class VideoConferenceProvider(ABC):
    """Port for creating calendar events that carry a video-call link.

    The provider is also responsible for emailing the attendees (invites,
    updates and cancellations).
    """

    @property
    @abstractmethod
    def provider_type(self) -> ConferenceProvider:
        pass

    @abstractmethod
    def get_connected_account_email(self, user_id: UUID) -> str | None:
        """Account email of the user, or ``None`` when not connected."""
        pass

    @abstractmethod
    def create_event(self, owner_user_id: UUID, event: ConferenceEvent) -> ConferenceEventResult:
        pass

    @abstractmethod
    def update_event(
        self, owner_user_id: UUID, event_id: str, event: ConferenceEvent
    ) -> str | None:
        """Patch the event. Returns the Meet link when ``event.with_meet`` is
        set and the event has one (also how Meet is added to an existing event)."""
        pass

    @abstractmethod
    def cancel_event(
        self, owner_user_id: UUID, event_id: str, notify_attendees: bool = True
    ) -> None:
        pass
