from dataclasses import dataclass
from uuid import UUID

RECORD_LEAD = "lead"
RECORD_CONTACT = "contact"
RECORD_ACCOUNT = "account"

KIND_EMAIL = "email"
KIND_PHONE = "phone"


@dataclass(frozen=True)
class ContactPointMatch:
    """An existing record that already uses an email / phone number."""

    record_type: str  # lead | contact | account
    record_id: UUID
    record_name: str
    kind: str  # email | phone
    value: str  # the value as entered by the person checking
