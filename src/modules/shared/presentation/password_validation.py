"""One password policy for every flow that sets a password through the API.

The rules are Django's ``AUTH_PASSWORD_VALIDATORS`` (see ``config/settings.py``):
minimum length, not a commonly used password, not entirely numeric, and not
too similar to the person's email or name. The same validators already guard
the ``create_platform_admin`` command, so the API and the command now agree.

Serializers use :func:`password_errors` and raise their own ``ValidationError``
with the returned messages, so a weak password is answered with a normal 400
whose body is ``{"<password field>": ["message", ...]}``, the same shape as the
existing ``min_length`` error.
"""

from types import SimpleNamespace

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


def password_errors(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> list[str]:
    """Why ``password`` is not acceptable (empty list when it is fine).

    ``email`` / ``name`` let the similarity validator reject a password built
    from the person's own details. Pass them whenever they are known (account
    creation); flows that only know the password (reset by token, reset by an
    admin) skip that one check and still enforce the others.
    """
    user = SimpleNamespace(email=email, name=name) if (email or name) else None
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        return list(error.messages)
    return []
