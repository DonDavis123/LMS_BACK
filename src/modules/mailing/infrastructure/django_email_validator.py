from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def is_valid_email(address: str) -> bool:
    """``True`` when Django's ``validate_email`` accepts the address."""
    try:
        validate_email(address)
    except ValidationError:
        return False
    return True
