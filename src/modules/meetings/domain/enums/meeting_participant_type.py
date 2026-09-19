from enum import Enum


class MeetingParticipantType(str, Enum):
    LEAD = "LEAD"
    USER = "USER"
    CONTACT = "CONTACT"
