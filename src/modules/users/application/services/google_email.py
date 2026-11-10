import re

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_LENGTH = 254


def normalize_google_email(value: str | None) -> str | None:
    """Strip + lower-case; blank becomes None. Raises ValueError if invalid."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Enter a valid email address.")

    email = value.strip().lower()
    if not email:
        return None

    if len(email) > _MAX_LENGTH or not _EMAIL_PATTERN.match(email):
        raise ValueError("Enter a valid email address.")

    return email
