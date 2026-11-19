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


class DuplicateContactPointError(ValueError):
    """Raised when an email / phone already belongs to another record.

    A ``ValueError`` on purpose: the views already turn it into a 400 with
    ``{"detail": message}``.
    """

    def __init__(self, match: ContactPointMatch):
        label = "email address" if match.kind == KIND_EMAIL else "phone number"
        super().__init__(
            f'This {label} ({match.value}) is already used by the '
            f'{match.record_type} "{match.record_name}".'
        )
        self.match = match


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
            raise DuplicateContactPointError(matches[0])


def _unique(values, normalize, skip):
    seen, result = set(skip), []
    for value in values:
        key = normalize(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
