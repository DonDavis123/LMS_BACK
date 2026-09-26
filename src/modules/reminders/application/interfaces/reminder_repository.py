from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.reminders.domain.entities.reminder import Reminder


class ReminderRepository(ABC):

    @abstractmethod
    def save(self, reminder: Reminder) -> Reminder:
        pass

    @abstractmethod
    def get_by_id(self, reminder_id: UUID) -> Reminder | None:
        pass

    @abstractmethod
    def get_by_user(self, user_id: UUID) -> list[Reminder]:
        pass

    @abstractmethod
    def get_by_task(self, task_id: UUID) -> list[Reminder]:
        pass

    @abstractmethod
    def get_by_meeting(self, meeting_id: UUID) -> list[Reminder]:
        pass

    @abstractmethod
    def get_due(self, as_of: datetime) -> list[Reminder]:
        pass

    @abstractmethod
    def delete_by_id(self, reminder_id: UUID) -> bool:
        pass
