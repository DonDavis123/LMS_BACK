from src.modules.shared.application.services.duplicate_guard import (
    DuplicateContactPointError,
)


def error_body(error: Exception) -> dict:
    """Body for a 400 caused by a ``ValueError`` raised in a use case.

    Always ``{"detail": str}``. When several values were rejected together
    (e.g. a duplicate email *and* a duplicate phone) it also carries
    ``errors``: one message per problem, so the form can list them all.
    """
    body = {"detail": str(error)}
    if isinstance(error, DuplicateContactPointError):
        body["errors"] = list(error.messages)
    return body
