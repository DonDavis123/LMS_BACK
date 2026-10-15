from rest_framework import status
from rest_framework.response import Response

from src.modules.users.infrastructure.persistence.current_user_reader import (
    DjangoCurrentUserReader,
)


def load_actor(request):
    """The authenticated platform admin as a domain user (not company-scoped)."""
    user = DjangoCurrentUserReader().get_by_id(request.user.id)
    if user is None:
        raise ValueError("User not found.")
    return user


def error_response(error: ValueError) -> Response:
    message = str(error)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if message in {"Company not found.", "User not found."}
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": message}, status=status_code)
