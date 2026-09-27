from enum import Enum


class NotificationType(str, Enum):
    REMINDER = "REMINDER"
    TASK_DUE_ONE_DAY = "TASK_DUE_ONE_DAY"
    TASK_DUE_TODAY = "TASK_DUE_TODAY"
    MEETING_ONE_DAY = "MEETING_ONE_DAY"
    MEETING_TODAY = "MEETING_TODAY"
