from enum import Enum


class TimelineEntityType(str, Enum):
    LEAD = "LEAD"
    CONTACT = "CONTACT"
    ACCOUNT = "ACCOUNT"
