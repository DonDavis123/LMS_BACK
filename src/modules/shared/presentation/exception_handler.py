import logging
import math

from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_SERVER_ERROR = "Something went wrong on the server. Please try again."


def throttled_message(wait: float | None) -> str:
    """A readable 429 message (DRF's default quotes the wait in raw seconds)."""
    if wait is None:
        return "Too many requests. Please try again later."

    seconds = max(1, math.ceil(wait))
    if seconds < 60:
        return f"Too many requests. Please try again in {seconds} seconds."

    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        unit = "minute" if minutes == 1 else "minutes"
        return f"Too many requests. Please try again in about {minutes} {unit}."

    hours = math.ceil(minutes / 60)
    unit = "hour" if hours == 1 else "hours"
    return f"Too many requests. Please try again in about {hours} {unit}."


def api_exception_handler(exc, context):
    """DRF exception handler that never lets an API call answer with HTML.

    Everything DRF already understands (validation, auth, permission, 404,
    throttling, ...) is handled exactly as before (a 429 only gets a more
    readable ``detail``). Anything else would
    normally bubble up to Django's default 500 page, which is HTML: the
    frontend cannot read a ``detail`` from it and shows an "unknown error".
    Such errors are logged with their traceback and answered with the same
    ``{"detail": ...}`` JSON shape as every other error, without leaking
    internals.
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
        if isinstance(exc, Throttled):
            # Same {"detail": ...} shape and Retry-After header as before,
            # with a message a person can read.
            response.data = {"detail": throttled_message(exc.wait)}
        return response

    view = context.get("view")
    request = context.get("request")
    logger.exception(
        "Unhandled error in %s %s (%s)",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        view.__class__.__name__ if view is not None else "unknown view",
        exc_info=exc,
    )
    return Response(
        {"detail": GENERIC_SERVER_ERROR},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
