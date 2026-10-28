"""Helpers that reshape messy rows before they are validated.

Pure functions: no Django, no database. Anything that can produce a warning
returns ``(value, warnings)``; each warning is a dict
``{code, field, value, message, how_to_fix}`` that the caller attaches to the
row number. Nothing here ever raises or truncates user data.
"""

from __future__ import annotations

import difflib
import re

from src.modules.picklists.domain.entities.picklist_catalog import SYSTEM_VALUE

from .lead_import_cleaning import (
    clean_phone,
    collapse_whitespace,
    is_blank_like,
    to_text,
)
from .lead_import_fields import normalize_header
from .lead_import_options import BLANK_VALUE, ImportOptions
from .lead_import_validation import PicklistSnapshot

MAX_DESCRIPTION_CHARS = 10_000
MIN_PHONE_DIGITS = 7
MAX_SUGGESTIONS = 3

CODE_PHONE_TOO_SHORT = "phone_too_short"
CODE_DESCRIPTION_VERY_LONG = "description_very_long"

# Comma, slash, semicolon, ampersand, line breaks and the word "and".
# Never spaces: "+974 7706 0555" and "73561 15925" are single numbers.
_PHONE_SPLIT_RE = re.compile(r"[,/;&\n\r]+|\band\b", re.IGNORECASE)
_NON_DIGITS_RE = re.compile(r"\D")

_PHONE_FIELDS = ("mobile_number", "phone")


def _warning(code, field, value, message, how_to_fix) -> dict:
    return {
        "code": code,
        "field": field,
        "value": value,
        "message": message,
        "how_to_fix": how_to_fix,
    }


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _loose(value) -> str:
    """Whitespace- and case-insensitive form used to compare dropdown values."""
    return " ".join(str(value).split()).casefold()


# ---------------------------------------------------------------------------
# Phones
# ---------------------------------------------------------------------------

def split_phones(raw) -> list[str]:
    """Split a cell holding several numbers.

    ``"9895500700 / 9388077077"`` -> two numbers;
    ``"9495674316,+974 7706 0555"`` -> two numbers;
    ``"+974 7706 0555"`` stays whole.
    """
    if raw is None:
        return []
    pieces = _PHONE_SPLIT_RE.split(str(raw))
    return [piece.strip() for piece in pieces if piece and piece.strip()]


def _clean_numbers(raw) -> list[str]:
    numbers = []
    for piece in split_phones(raw):
        value, _warning_code = clean_phone(piece)
        if value:
            numbers.append(value)
    return numbers


def apply_phone_splitting(cleaned: dict, mapped_field_keys, raw_values: dict | None = None):
    """Spread several numbers in a phone cell over the row.

    For each mapped phone field (Mobile Number, then Phone) the FIRST number
    stays in it. The second goes into the other phone field only when that
    field is not mapped (and still empty). Any remaining numbers are added to
    the description as a line ``Other numbers: ...``. Every number after the
    first is also stored in ``cleaned["_extra_phones"]`` so duplicate matching
    can use it. Numbers need not be 10 digits; fewer than 7 digits is only a
    warning (such a number can never be matched to another lead).

    ``clean_phone`` strips the separators this function splits on, so pass the
    RAW cell text of the phone fields in ``raw_values`` (``{field: raw}``);
    without it the already-cleaned values are used. Each number is cleaned
    here. Returns ``(new cleaned dict, warnings)``; the input is not changed.
    """
    result = dict(cleaned)
    mapped = set(mapped_field_keys)
    warnings: list[dict] = []
    extras: list[str] = []
    leftovers: list[str] = []

    for field in _PHONE_FIELDS:
        if field not in mapped:
            continue
        source = raw_values[field] if raw_values and field in raw_values else cleaned.get(field)
        numbers = _clean_numbers(source)
        if not numbers:
            continue

        result[field] = numbers[0]
        rest = numbers[1:]
        extras.extend(rest)

        other = "phone" if field == "mobile_number" else "mobile_number"
        if rest and other not in mapped and _blank(result.get(other)):
            result[other] = rest[0]
            rest = rest[1:]
        leftovers.extend(rest)

        for number in numbers:
            digits = len(_NON_DIGITS_RE.sub("", number))
            if 0 < digits < MIN_PHONE_DIGITS:
                warnings.append(
                    _warning(
                        CODE_PHONE_TOO_SHORT,
                        field,
                        number,
                        f"The number '{number}' has only {digits} digits, so it cannot be "
                        "used to find duplicates.",
                        "Check the number in your file; it was imported as written.",
                    )
                )

    if leftovers:
        line = "Other numbers: " + ", ".join(leftovers)
        existing = result.get("description")
        result["description"] = line if _blank(existing) else f"{existing}\n{line}"
    if extras:
        result["_extra_phones"] = extras
    return result, warnings


# ---------------------------------------------------------------------------
# Description, name
# ---------------------------------------------------------------------------

def append_extra_columns(description, row_values: dict, extra_columns):
    """Add a ``Label: value`` line per non-blank extra column to the description.

    ``row_values`` is ``{file header: raw text}``; ``extra_columns`` is
    ``[{column, label}]``. Returns ``(description or None, warnings)``. A
    description over 10,000 characters is kept in full and only warned about.
    """
    lines = []
    for extra in extra_columns or []:
        column = extra.get("column")
        value = collapse_whitespace(to_text((row_values or {}).get(column)))
        if is_blank_like(value):
            continue
        lines.append(f"{extra.get('label') or column}: {value}")

    base = None if _blank(description) else str(description)
    if lines:
        text = "\n".join(lines)
        base = text if base is None else f"{base}\n{text}"

    warnings: list[dict] = []
    if base is not None and len(base) > MAX_DESCRIPTION_CHARS:
        warnings.append(
            _warning(
                CODE_DESCRIPTION_VERY_LONG,
                "description",
                None,
                f"The description is {len(base):,} characters long (over "
                f"{MAX_DESCRIPTION_CHARS:,}). It was kept in full.",
                "Remove extra columns you do not need if you want shorter descriptions.",
            )
        )
    return base, warnings


def fill_name_from_company(cleaned: dict) -> dict:
    """For ``use_company_as_name``: a blank Name takes the Company Name."""
    result = dict(cleaned)
    if _blank(result.get("name")) and not _blank(result.get("company_name")):
        result["name"] = result["company_name"]
    return result


# ---------------------------------------------------------------------------
# Dropdown values
# ---------------------------------------------------------------------------

def apply_value_mapping(field: str, cleaned_value, options, picklists: PicklistSnapshot):
    """Rescue a dropdown value that is not one of the company's options.

    Only values ``picklists.resolve`` rejects (unknown or hidden options) are
    touched, in this order: the user's ``value_mapping`` for the field, where
    ``"__blank__"`` means ``"None"``; then ``unknown_values_as_blank``. Anything
    else is returned unchanged so validation reports it.
    """
    if isinstance(options, dict):
        options = ImportOptions.from_dict(options)
    _resolved, reason = picklists.resolve(field, cleaned_value)
    if reason is None:
        return cleaned_value

    mapping = (options.value_mapping or {}).get(field) or {}
    key = _loose(cleaned_value)
    target = mapping.get(cleaned_value)
    if target is None:
        target = next((v for raw, v in mapping.items() if _loose(raw) == key), None)
    if target is not None:
        return SYSTEM_VALUE if target == BLANK_VALUE else target
    if options.unknown_values_as_blank:
        return SYSTEM_VALUE
    return cleaned_value


def _suggestions(value: str, active_options: list[str]) -> list[str]:
    options = [o for o in active_options if o != SYSTEM_VALUE]
    wanted = normalize_header(value)
    if not wanted or not options:
        return []
    padded_wanted = f" {wanted} "

    found: list[str] = []
    # Whole-word containment either way ("Web" <-> "Web Research").
    for option in options:
        norm = normalize_header(option)
        if len(norm) >= 3 and len(wanted) >= 3 and (
            f" {norm} " in padded_wanted or padded_wanted in f" {norm} "
        ):
            found.append(option)

    by_norm: dict[str, str] = {}
    for option in options:
        by_norm.setdefault(normalize_header(option), option)
    for norm in difflib.get_close_matches(wanted, list(by_norm), n=MAX_SUGGESTIONS, cutoff=0.6):
        found.append(by_norm[norm])

    unique: list[str] = []
    for option in found:
        if option not in unique:
            unique.append(option)
    return unique[:MAX_SUGGESTIONS]


def collect_unrecognized(rows_cleaned, mapped_picklist_fields, picklists: PicklistSnapshot) -> dict:
    """Dropdown values in the file that are not the company's options.

    ``{field: [{value, count, suggestions}]}``, most frequent first, with up to
    3 suggestions per value taken from the company's own active options
    (difflib and whole-word containment only; no AI). Blank cells are not
    reported.
    """
    report: dict[str, list[dict]] = {}
    for field in mapped_picklist_fields:
        groups: dict[str, dict] = {}
        for row in rows_cleaned:
            value = row.get(field)
            _resolved, reason = picklists.resolve(field, value)
            if reason is None:
                continue
            entry = groups.setdefault(
                _loose(value), {"value": " ".join(str(value).split()), "count": 0}
            )
            entry["count"] += 1
        if not groups:
            continue
        active = picklists.active_options(field)
        report[field] = [
            {**entry, "suggestions": _suggestions(entry["value"], active)}
            for entry in sorted(
                groups.values(), key=lambda e: (-e["count"], e["value"].casefold())
            )
        ]
    return report
