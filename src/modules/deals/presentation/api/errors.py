from rest_framework import status
from rest_framework.response import Response


def _first_message(errors) -> str:
    if isinstance(errors, dict):
        for key, value in errors.items():
            message = _first_message(value)
            return message if key == "non_field_errors" else f"{key}: {message}"
    if isinstance(errors, (list, tuple)):
        return _first_message(errors[0]) if errors else "Invalid value."
    return str(errors)


def validation_error_response(serializer) -> Response:
    """Answer a failed serializer with the module's {"detail": "..."} shape."""
    return Response(
        {"detail": _first_message(serializer.errors)},
        status=status.HTTP_400_BAD_REQUEST,
    )
