import re
from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.users.application.interfaces.user_repository import UserRepository

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ROLE_HOST = "host"
ROLE_PARTICIPANT = "participant"
ROLE_RELATED = "related"

REASON_NO_EMAIL = "no_email"
REASON_INVALID_EMAIL = "invalid_email"


@dataclass(frozen=True)
class SkippedRecipient:
    """Someone who should have been emailed but has no usable address."""

    name: str
    kind: str  # USER, LEAD or CONTACT
    role: str  # host, participant or related
    reason: str  # no_email or invalid_email

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.kind, "role": self.role, "reason": self.reason}


@dataclass(frozen=True)
class MeetingRecipients:
    emails: tuple[str, ...]
    skipped: tuple[SkippedRecipient, ...]


class MeetingRecipientResolver:
    """Works out who hears about a meeting.

    Recipients are the host, every participant (users, leads, contacts) and
    every "Related To" lead/contact. People without a usable email are not
    dropped silently: they come back in ``skipped`` so the API can report them.
    """

    def __init__(self, meeting_repository: MeetingRepository, user_repository: UserRepository):
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository

    def resolve(
        self,
        meeting: Meeting,
        exclude_user_ids: frozenset[UUID] | set[UUID] = frozenset(),
        exclude_emails: frozenset[str] | set[str] = frozenset(),
    ) -> MeetingRecipients:
        # (person key, email, name, kind, role)
        candidates: list[tuple[tuple[str, UUID], str | None, str, str, str]] = []

        host = self.user_repository.get_by_id(meeting.host_id)
        if host is not None and host.is_active:
            candidates.append(
                (("USER", host.id), host.google_email or host.email, host.name, "USER", ROLE_HOST)
            )

        detail = self.meeting_repository.get_by_id_with_details(meeting.id)
        if detail is not None:
            for participant in detail.participants:
                kind = participant.participant_type.value
                candidates.append(
                    ((kind, participant.id), participant.email, participant.name, kind, ROLE_PARTICIPANT)
                )
            for record in detail.related_to:
                kind = record.record_type.value
                candidates.append(
                    ((kind, record.id), record.email, record.name, kind, ROLE_RELATED)
                )

        excluded_emails = {email.strip().lower() for email in exclude_emails if email}
        for user_id in exclude_user_ids:
            user = self.user_repository.get_by_id(user_id)
            if user is not None:
                excluded_emails.add((user.email or "").strip().lower())
                excluded_emails.add((user.google_email or "").strip().lower())
        excluded_emails.discard("")

        seen_people: set[tuple[str, UUID]] = set()
        seen_emails: set[str] = set()
        emails: list[str] = []
        skipped: list[SkippedRecipient] = []

        for key, raw_email, name, kind, role in candidates:
            if key in seen_people:
                continue  # same lead listed as participant and as related
            seen_people.add(key)
            if kind == "USER" and key[1] in exclude_user_ids:
                continue

            email = (raw_email or "").strip()
            if not email:
                skipped.append(SkippedRecipient(name, kind, role, REASON_NO_EMAIL))
                continue
            if not _EMAIL_PATTERN.match(email):
                skipped.append(SkippedRecipient(name, kind, role, REASON_INVALID_EMAIL))
                continue

            lowered = email.lower()
            if lowered in excluded_emails or lowered in seen_emails:
                continue
            seen_emails.add(lowered)
            emails.append(email)

        return MeetingRecipients(tuple(emails), tuple(skipped))
