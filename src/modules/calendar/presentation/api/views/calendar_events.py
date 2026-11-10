from datetime import datetime
from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.calendar.presentation.api.dependencies.calendar_dependencies import (
    get_calendar_events_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.calendar_event import CalendarEventSerializer


def _parse_datetime(name: str, raw: str | None) -> datetime:
    if not raw:
        raise ValueError(f"'{name}' is required.")

    # ``+`` in an offset is turned into a space by query-string decoding.
    try:
        parsed = datetime.fromisoformat(raw.strip().replace(" ", "+").replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"'{name}' must be an ISO 8601 date-time.")

    if parsed.tzinfo is None:
        raise ValueError(f"'{name}' must include a UTC offset.")

    return parsed


class CalendarEventsView(APIView):
    """GET /api/calendar/events/?start=&end=[&types=TASK,CALL][&scope=team][&owner_id=]"""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        params = request.query_params

        try:
            start = _parse_datetime("start", params.get("start"))
            end = _parse_datetime("end", params.get("end"))

            raw_types = params.get("types")
            types = (
                tuple(
                    item.strip().upper()
                    for item in raw_types.split(",")
                    if item.strip()
                )
                if raw_types
                else None
            )

            raw_owner = params.get("owner_id")
            try:
                owner_id = UUID(raw_owner) if raw_owner else None
            except ValueError:
                raise ValueError("'owner_id' must be a valid UUID.")

            events = get_calendar_events_use_case(get_tenant_context(request)).execute(
                current_user_id=request.user.id,
                current_user_role=request.user.role,
                start=start,
                end=end,
                types=types,
                scope=params.get("scope", "mine"),
                owner_id=owner_id,
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"results": CalendarEventSerializer(events, many=True).data},
            status=status.HTTP_200_OK,
        )
