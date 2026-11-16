from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MeetingReminder:
    title: str
    start_at: datetime
    end_at: datetime
    meet_link: str
    host_name: str
    location: str | None = None
    description: str | None = None


class MeetingReminderNotifier(ABC):
    """Port: tell one participant that a meeting is about to start."""

    @abstractmethod
    def send(self, recipient_email: str, reminder: MeetingReminder) -> None:
        """Raise any exception if the email could not be handed off."""
