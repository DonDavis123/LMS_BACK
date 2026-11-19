from collections.abc import Iterable
from uuid import UUID

from src.modules.shared.application.dto.contact_point_match import (
    KIND_EMAIL,
    ContactPointMatch,
)
from src.modules.shared.application.interfaces.contact_point_directory import (
    ContactPointDirectory,
)
from src.modules.shared.application.services.contact_field_rules import (
    normalize_email,
    normalize_phone,
)


def _describe_match(match: ContactPointMatch) -> str:
    label = "email address" if match.kind == KIND_EMAIL else "phone number"
    return (
        f'This {label} ({match.value}) is already used by the '
        f'{match.record_type} "{match.record_name}".'
    )


class DuplicateContactPointError(ValueError):
    """Raised when an email / phone already belongs to another record.

    A ``ValueError`` on purpose: the views already turn it into a 400 with
    ``{"detail": message}``. Every conflicting value is reported (one message
    each in ``messages``) so the form can show them all at once; ``str()``
    joins them so callers that only read ``detail`` still get everything.
    """

    def __init__(self, matches: Iterable[ContactPointMatch]):
        if isinstance(matches, ContactPointMatch):
            matches = [matches]
        self.matches = _first_match_per_value(matches)
        self.messages = [_describe_match(m) for m in self.matches]
        super().__init__(" ".join(self.messages))
        self.match = self.matches[0]


def _first_match_per_value(matches: Iterable[ContactPointMatch]):
    """One match per entered value (a value may hit several records)."""
    seen, result = set(), []
    for match in matches:
        key = (match.kind, match.value.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(match)
    return result


class DuplicateGuard:
    """One rule for leads, contacts and accounts: an email or phone number
    may only belong to one record across all three."""

    def __init__(self, directory: ContactPointDirectory):
        self.directory = directory

    def find(
        self,
        *,
        emails: Iterable[str | None] = (),
        phones: Iterable[str | None] = (),
        exclude: tuple[str, UUID] | None = None,
        previous_emails: Iterable[str | None] = (),
        previous_phones: Iterable[str | None] = (),
    ) -> list[ContactPointMatch]:
        """Matches for the values that are new.

        Values equal to one of ``previous_*`` (what the record already had)
        are skipped, so editing an old record that already shares a number
        with another record is not blocked until that number is changed.
        """
        old_emails = {normalize_email(v) for v in previous_emails}
        old_phones = {normalize_phone(v) for v in previous_phones}

        new_emails = _unique(
            (v.strip() for v in emails if normalize_email(v)),
            normalize_email,
            old_emails,
        )
        new_phones = _unique(
            (v.strip() for v in phones if normalize_phone(v)),
            normalize_phone,
            old_phones,
        )
        if not new_emails and not new_phones:
            return []
        return self.directory.find_matches(
            emails=new_emails, phones=new_phones, exclude=exclude
        )

    def ensure_unique(self, **kwargs) -> None:
        matches = self.find(**kwargs)
        if matches:
            raise DuplicateContactPointError(matches)


def _unique(values, normalize, skip):
    seen, result = set(skip), []
    for value in values:
        key = normalize(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
