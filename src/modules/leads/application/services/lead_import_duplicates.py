"""Duplicate detection for lead import.

Pure functions: no Django, no database. The existing-lead index is read once
per import by ``LeadRepository.get_dedupe_index()`` and handed in.

Matching rule (the same everywhere in this module):
  1. A row WITH an email matches on email only.
  2. A row WITHOUT an email matches on phone / mobile number only.
  3. Name and company are never used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NEW = "NEW"
DUPLICATE_EXISTING = "DUPLICATE_EXISTING"
DUPLICATE_IN_FILE = "DUPLICATE_IN_FILE"

MATCHED_ON_EMAIL = "email"
MATCHED_ON_PHONE = "phone"

PHONE_MATCH_DIGITS = 10
PHONE_MIN_DIGITS = 7

_NON_DIGITS = re.compile(r"\D")


def normalize_email(value: object) -> str | None:
    """Trimmed, lower-case email; ``None`` when blank."""
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def normalize_phone(value: object) -> str | None:
    """Digits only; the LAST 10 when there are 10 or more (so country codes
    and leading zeros do not matter); ``None`` below 7 digits, which is too
    short to match safely."""
    if value is None:
        return None
    digits = _NON_DIGITS.sub("", str(value))
    if len(digits) < PHONE_MIN_DIGITS:
        return None
    if len(digits) >= PHONE_MATCH_DIGITS:
        return digits[-PHONE_MATCH_DIGITS:]
    return digits


def _phone_keys(cleaned: dict) -> list[str]:
    """Normalized phone then mobile number, without blanks or repeats."""
    keys: list[str] = []
    for field in ("phone", "mobile_number"):
        key = normalize_phone(cleaned.get(field))
        if key is not None and key not in keys:
            keys.append(key)
    return keys


@dataclass(frozen=True)
class DuplicateMatch:
    kind: str = NEW
    matched_on: str | None = None  # "email" | "phone"
    lead_id: object | None = None
    name: str | None = None
    is_converted: bool = False
    first_row: int | None = None  # in-file duplicates only

    @property
    def is_duplicate(self) -> bool:
        return self.kind != NEW


def in_file_match(first_row: int, row_cleaned: dict) -> DuplicateMatch:
    """The match for a row that ``find_in_file_duplicates`` flagged."""
    matched_on = (
        MATCHED_ON_EMAIL
        if normalize_email((row_cleaned or {}).get("email"))
        else MATCHED_ON_PHONE
    )
    return DuplicateMatch(
        kind=DUPLICATE_IN_FILE, matched_on=matched_on, first_row=first_row
    )


def find_in_file_duplicates(rows) -> dict[int, int]:
    """``{row_number: first_row_number}`` for every repeated row.

    ``rows`` is the stored row list in file order: dicts with ``row_number``
    and ``cleaned`` ({field: value}). The first occurrence is kept; later
    ones are flagged and point at it.

    - A row with an email is a duplicate when an earlier row has the same
      normalized email. Its phone is ignored.
    - A row without an email is a duplicate when an earlier row WITHOUT an
      email shares a normalized phone or mobile number.
    """
    first_by_email: dict[str, int] = {}
    first_by_phone: dict[str, int] = {}
    duplicates: dict[int, int] = {}

    for row in rows:
        row_number = row["row_number"]
        cleaned = row.get("cleaned") or {}

        email = normalize_email(cleaned.get("email"))
        if email is not None:
            first = first_by_email.setdefault(email, row_number)
            if first != row_number:
                duplicates[row_number] = first
            continue

        keys = _phone_keys(cleaned)
        first = next((first_by_phone[k] for k in keys if k in first_by_phone), None)
        if first is not None:
            duplicates[row_number] = first
        # A flagged row still registers its other numbers, pointing at the
        # first occurrence, so a third row sharing only that number is caught.
        for key in keys:
            first_by_phone.setdefault(key, first if first is not None else row_number)

    return duplicates


def classify(row_cleaned: dict, index: dict) -> DuplicateMatch:
    """NEW, or DUPLICATE_EXISTING with the matched lead's details.

    ``index`` is ``LeadRepository.get_dedupe_index()``:
    ``{"emails": {email: info}, "phones": {last10: info}}`` where ``info`` is
    ``{id, name, is_converted}``.
    """
    cleaned = row_cleaned or {}
    email = normalize_email(cleaned.get("email"))

    if email is not None:
        info = (index.get("emails") or {}).get(email)
        return _existing(info, MATCHED_ON_EMAIL)

    phones = index.get("phones") or {}
    for key in _phone_keys(cleaned):
        info = phones.get(key)
        if info is not None:
            return _existing(info, MATCHED_ON_PHONE)
    return DuplicateMatch()


def _existing(info: dict | None, matched_on: str) -> DuplicateMatch:
    if info is None:
        return DuplicateMatch()
    return DuplicateMatch(
        kind=DUPLICATE_EXISTING,
        matched_on=matched_on,
        lead_id=info.get("id"),
        name=info.get("name"),
        is_converted=bool(info.get("is_converted")),
    )


_CHOICES = (
    "Skip (leave the existing lead as it is), "
    "Update existing (fill it with this row's values) or "
    "Create anyway (add this row as a new lead)"
)


def describe_duplicate(match: DuplicateMatch) -> tuple[str, str]:
    """``(message, how_to_fix)`` in plain English for a duplicate match."""
    what = "email" if match.matched_on == MATCHED_ON_EMAIL else "phone number"

    if match.kind == DUPLICATE_IN_FILE:
        return (
            f"Same {what} as row {match.first_row} in this file.",
            "Delete one of the two rows in your file, or choose Create anyway "
            "to import both. Only the first of the repeated rows is kept "
            "when you choose Skip or Update existing.",
        )

    who = f" ({match.name})" if match.name else ""
    message = f"Same {what} as an existing lead{who}."
    if match.is_converted:
        return (
            f"{message} That lead has already been converted and cannot be changed.",
            "Choose one action for the whole file: Skip (leave it as it is), "
            "Update existing (converted leads are still skipped, never "
            "changed) or Create anyway (add this row as a new lead).",
        )
    return message, f"Choose one action for the whole file: {_CHOICES}."


def duplicate_problem(match: DuplicateMatch, *, row_number, column, field, value):
    """A ``RowProblem`` carrying ``describe_duplicate``'s text.

    Code is ``converted_locked`` for a converted lead, else ``duplicate``.
    """
    # Imported here so this module stays free of Django/DRF at import time.
    from .lead_import_validation import (
        CODE_CONVERTED_LOCKED,
        CODE_DUPLICATE,
        RowProblem,
    )

    message, how_to_fix = describe_duplicate(match)
    return RowProblem(
        row_number=row_number,
        column=column,
        field=field,
        value=value,
        code=CODE_CONVERTED_LOCKED if match.is_converted else CODE_DUPLICATE,
        message=f"Row {row_number}: {message}",
        how_to_fix=how_to_fix,
    )
