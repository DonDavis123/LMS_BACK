from enum import Enum


class RecordType(str, Enum):
    """Kind of CRM record a recipient or a skipped entry belongs to.

    Recipients are only ever CONTACT or LEAD; ACCOUNT appears on skipped
    entries (an account has no address of its own).
    """

    CONTACT = "CONTACT"
    LEAD = "LEAD"
    ACCOUNT = "ACCOUNT"
