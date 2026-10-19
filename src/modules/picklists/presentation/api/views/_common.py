from rest_framework import status
from rest_framework.response import Response

from src.modules.picklists.domain.exceptions import PicklistOptionInUseError


def error_response(error: ValueError) -> Response:
    if isinstance(error, PicklistOptionInUseError):
        return Response(
            {
                "detail": str(error),
                "code": "OPTION_IN_USE",
                "usage_count": error.usage_count,
            },
            status=status.HTTP_409_CONFLICT,
        )

    message = str(error)
    not_found = message in {
        "Option not found.",
        "Replacement option not found.",
        "Unknown picklist field.",
        "Unknown picklist module.",
    }
    return Response(
        {"detail": message},
        status=status.HTTP_404_NOT_FOUND if not_found else status.HTTP_400_BAD_REQUEST,
    )
