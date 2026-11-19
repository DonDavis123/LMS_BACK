"""Pure format rules for phone numbers and email addresses.

No Django/DRF imports here, so the same rules can be reused by serializers,
the live-validation endpoint and any future use case.
"""

import re

PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15  # E.164 upper bound
PHONE_MAX_LENGTH = 20
EMAIL_MAX_LENGTH = 254

PHONE_REQUIRED_MESSAGE = "Phone number is required."
PHONE_INVALID_MESSAGE = (
    "Enter a valid phone number (7 to 15 digits, optional leading +)."
)
PHONE_CHARS_MESSAGE = (
    "Phone number can only contain digits, spaces, + ( ) - and ."
)
EMAIL_INVALID_MESSAGE = "Enter a valid email address."

_PHONE_ALLOWED = re.compile(r"^\+?[\d\s().\-]+$")
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def phone_error(value: str | None) -> str | None:
    """Return an error message for a non-empty phone value, else ``None``."""
    text = (value or "").strip()
    if not text:
        return PHONE_REQUIRED_MESSAGE
    if len(text) > PHONE_MAX_LENGTH:
        return PHONE_INVALID_MESSAGE
    if not _PHONE_ALLOWED.match(text) or "+" in text[1:]:
        return PHONE_CHARS_MESSAGE
    digits = sum(ch.isdigit() for ch in text)
    if not PHONE_MIN_DIGITS <= digits <= PHONE_MAX_DIGITS:
        return PHONE_INVALID_MESSAGE
    return None


def email_error(value: str | None) -> str | None:
    """Return an error message for a non-empty email value, else ``None``."""
    text = (value or "").strip()
    if not text:
        return EMAIL_INVALID_MESSAGE
    if len(text) > EMAIL_MAX_LENGTH or ".." in text:
        return EMAIL_INVALID_MESSAGE
    local = text.split("@", 1)[0]
    if local.startswith(".") or local.endswith("."):
        return EMAIL_INVALID_MESSAGE
    if not _EMAIL_RE.match(text):
        return EMAIL_INVALID_MESSAGE
    return None
