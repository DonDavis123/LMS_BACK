"""Value cleaning for imported cells.

Pure functions, no Django. Every function returns ``(value, warning_code)``
and NEVER raises, so one odd cell can never abort a whole import.

``warning_code`` is ``None`` when the value is fine. Codes that start with
``invalid_`` or ``negative_`` or ``not_whole_`` mean the value could not be
turned into what the field needs; in that case ``value`` is the cleaned
original text, so the error message can show the user what was found.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from .lead_import_fields import (
    KIND_BOOL,
    KIND_EMAIL,
    KIND_INT,
    KIND_OWNER,
    KIND_PHONE,
    KIND_PICKLIST,
    KIND_URL,
)

BLANK_LIKE = {"", "n/a", "na", "null", "-"}

CODE_INVALID_NUMBER = "invalid_number"
CODE_NOT_WHOLE_NUMBER = "not_whole_number"
CODE_NEGATIVE_NUMBER = "negative_number"
CODE_PHONE_CHARS_REMOVED = "phone_chars_removed"
CODE_CLEAN_FAILED = "clean_failed"
CODE_INVALID_CONVERTED = "invalid_converted"

_TRUE_WORDS = {"true", "yes", "y", "1", "converted", "x"}
_FALSE_WORDS = {"false", "no", "n", "0", "not converted"}

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_SCI_RE = re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")
_TRAILING_ZERO_RE = re.compile(r"^(\d+)\.0+$")
_CURRENCY_RE = re.compile(r"[\s$€£₹¥,]")
_PHONE_ALLOWED_RE = re.compile(r"[^0-9+()\-. ]")


def to_text(raw: object) -> str:
    """Any cell value as text (None -> "")."""
    if raw is None:
        return ""
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if isinstance(raw, datetime):
        if raw.time() == time(0, 0):
            return raw.date().isoformat()
        return raw.isoformat(sep=" ", timespec="seconds")
    if isinstance(raw, (date, time)):
        return raw.isoformat()
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        if raw != raw or raw in (float("inf"), float("-inf")):
            return ""
        if raw == int(raw) and abs(raw) < 1e18:
            return str(int(raw))
        text = repr(raw)
        if "e" in text.lower():
            try:
                text = format(Decimal(text), "f")
            except InvalidOperation:
                pass
        return text
    return str(raw)


def collapse_whitespace(text: str, multiline: bool = False) -> str:
    """Trim and collapse runs of whitespace (tabs and non-breaking spaces too).

    With ``multiline`` line breaks are kept (one per break, blank runs
    reduced to a single blank line) and trimmed at both ends.
    """
    text = text.replace(" ", " ").replace("﻿", "").replace("​", "")
    if not multiline:
        return re.sub(r"\s+", " ", text).strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.split("\n")]
    joined = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


def is_blank_like(text: str) -> bool:
    return text.strip().lower() in BLANK_LIKE


def _numeric_to_digits(text: str) -> str | None:
    """Turn an Excel numeric artefact into plain digits, else None.

    9.87654321E+9 -> 9876543210, 9876543210.0 -> 9876543210.
    """
    stripped = text.strip()
    m = _TRAILING_ZERO_RE.match(stripped)
    if m:
        return m.group(1)
    if _SCI_RE.match(stripped):
        try:
            number = Decimal(stripped)
            if number == number.to_integral_value():
                return format(number.to_integral_value(), "f")
        except InvalidOperation:
            return None
    return None


def clean_text(raw: object, multiline: bool = False):
    text = collapse_whitespace(to_text(raw), multiline)
    if is_blank_like(text):
        return None, None
    return text, None


def clean_email(raw: object):
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return None, None
    lowered = text.lower()
    if lowered.startswith("mailto:"):
        lowered = lowered[len("mailto:"):]
    lowered = lowered.strip("<>").strip()
    return (lowered or None), None


def clean_phone(raw: object):
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return None, None
    digits = _numeric_to_digits(text)
    if digits is not None:
        return digits, None
    cleaned = _PHONE_ALLOWED_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    warning = CODE_PHONE_CHARS_REMOVED if cleaned != text else None
    return (cleaned or None), warning


def clean_url(raw: object):
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return None, None
    if _SCHEME_RE.match(text) or " " in text:
        return text, None
    if "." in text and not text.lower().startswith("mailto:"):
        return "https://" + text, None
    return text, None


def clean_int(raw: object):
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return None, None
    compact = _CURRENCY_RE.sub("", text)
    digits = _numeric_to_digits(compact)
    candidate = digits if digits is not None else compact
    try:
        number = Decimal(candidate)
    except InvalidOperation:
        return text, CODE_INVALID_NUMBER
    if not number.is_finite():
        return text, CODE_INVALID_NUMBER
    if number != number.to_integral_value():
        return text, CODE_NOT_WHOLE_NUMBER
    value = int(number)
    if value < 0:
        return text, CODE_NEGATIVE_NUMBER
    return value, None


def clean_picklist(raw: object):
    # "None" is a real dropdown option in this CRM, so it is never blank-like.
    text = collapse_whitespace(to_text(raw))
    if text.lower() in {"", "n/a", "na", "null", "-"}:
        return None, None
    return text, None


def clean_owner(raw: object):
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return None, None
    return text, None


def clean_bool(raw: object):
    """The "Converted" column: yes/y/true/1/converted/x -> True;
    no/n/false/0/not converted or blank -> False; anything else keeps the
    original text with the ``invalid_converted`` code."""
    text = collapse_whitespace(to_text(raw))
    if is_blank_like(text):
        return False, None
    word = text.lower()
    if word in _TRUE_WORDS:
        return True, None
    if word in _FALSE_WORDS:
        return False, None
    return text, CODE_INVALID_CONVERTED


_CLEANERS = {
    KIND_BOOL: clean_bool,
    KIND_EMAIL: clean_email,
    KIND_PHONE: clean_phone,
    KIND_URL: clean_url,
    KIND_INT: clean_int,
    KIND_PICKLIST: clean_picklist,
    KIND_OWNER: clean_owner,
}


def clean_value(field_kind: str, raw: object, multiline: bool = False):
    """Clean one cell for a field of the given kind. Never raises."""
    try:
        cleaner = _CLEANERS.get(field_kind)
        if cleaner is not None:
            return cleaner(raw)
        return clean_text(raw, multiline=multiline)
    except Exception:  # noqa: BLE001 - cleaning must never abort an import
        try:
            fallback = collapse_whitespace(to_text(raw), multiline)
        except Exception:  # noqa: BLE001
            fallback = ""
        return (fallback or None), CODE_CLEAN_FAILED
