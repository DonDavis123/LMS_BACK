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


@dataclass(frozen=True)
class ConferenceEventResult:
    event_id: str
    meet_link: str


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
    def update_event(self, owner_user_id: UUID, event_id: str, event: ConferenceEvent) -> None:
        pass

    @abstractmethod
    def cancel_event(self, owner_user_id: UUID, event_id: str) -> None:
        pass
