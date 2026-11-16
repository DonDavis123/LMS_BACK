from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

# What the email is about.
KIND_INVITATION = "invitation"
KIND_UPDATE = "update"
KIND_CANCELLATION = "cancellation"
KIND_REMINDER = "reminder"


@dataclass(frozen=True)
class MeetingReminder:
    """Content of one meeting email (invitation, update, cancellation or
    reminder). Every email carries the meeting heading and description."""

    title: str
    start_at: datetime
    end_at: datetime
    host_name: str
    # None when the meeting has no Google Meet link.
    meet_link: str | None = None
    location: str | None = None
    description: str | None = None
    kind: str = KIND_REMINDER
    is_all_day: bool = False


class MeetingReminderNotifier(ABC):
    """Port: email one person about a meeting."""

    @abstractmethod
    def send(self, recipient_email: str, reminder: MeetingReminder) -> None:
        """Raise any exception if the email could not be handed off."""
