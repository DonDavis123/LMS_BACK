from enum import Enum


class RecordType(str, Enum):
    """Kind of CRM record an email was composed for."""

    CONTACT = "CONTACT"
    LEAD = "LEAD"
