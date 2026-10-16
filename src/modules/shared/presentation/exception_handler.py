import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_SERVER_ERROR = "Something went wrong on the server. Please try again."


def api_exception_handler(exc, context):
    """DRF exception handler that never lets an API call answer with HTML.

    Everything DRF already understands (validation, auth, permission, 404,
    throttling, ...) is handled exactly as before. Anything else would
    normally bubble up to Django's default 500 page, which is HTML: the
    frontend cannot read a ``detail`` from it and shows an "unknown error".
    Such errors are logged with their traceback and answered with the same
    ``{"detail": ...}`` JSON shape as every other error, without leaking
    internals.
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
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
