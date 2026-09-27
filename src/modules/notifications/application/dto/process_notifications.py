from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessNotificationsResult:
    reminders_processed: int = 0
    task_notifications_created: int = 0
    meeting_notifications_created: int = 0
    duplicates_skipped: int = 0
    expired_notifications_deleted: int = 0
    failures: int = 0
