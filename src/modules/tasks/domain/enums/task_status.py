from enum import Enum


class TaskStatus(str, Enum):
    NOT_STARTED = "Not Started"
    DEFERRED = "Deferred"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    WAITING_FOR_INPUT = "Waiting for Input"
