from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessNotificationsResult:
    reminders_processed: int = 0
    reminders_deleted: int = 0
    task_notifications_created: int = 0
    meeting_notifications_created: int = 0
    duplicates_skipped: int = 0
    expired_notifications_deleted: int = 0
    failures: int = 0

    def __add__(self, other: "ProcessNotificationsResult") -> "ProcessNotificationsResult":
        return ProcessNotificationsResult(
            reminders_processed=self.reminders_processed + other.reminders_processed,
            reminders_deleted=self.reminders_deleted + other.reminders_deleted,
            task_notifications_created=(
                self.task_notifications_created + other.task_notifications_created
            ),
            meeting_notifications_created=(
                self.meeting_notifications_created + other.meeting_notifications_created
            ),
            duplicates_skipped=self.duplicates_skipped + other.duplicates_skipped,
            expired_notifications_deleted=(
                self.expired_notifications_deleted + other.expired_notifications_deleted
            ),
            failures=self.failures + other.failures,
        )
