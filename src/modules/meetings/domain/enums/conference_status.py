from enum import Enum


class ConferenceStatus(str, Enum):
    NONE = "none"
    CREATED = "created"
    FAILED = "failed"
