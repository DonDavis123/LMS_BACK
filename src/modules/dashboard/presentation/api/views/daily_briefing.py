from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.dashboard.application.interfaces.daily_briefing_generator import (
    DailyBriefingError,
    DailyBriefingUnavailableError,
)
from src.modules.dashboard.presentation.api.dependencies.dashboard_dependencies import (
    get_daily_briefing_use_case,
)
from src.modules.dashboard.presentation.api.serializers import (
    DailyBriefingRequestSerializer,
    DailyBriefingSerializer,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class DailyBriefingView(APIView):
    """The AI plan for the caller's day (the greeting card's "Plan my day").

    ``POST`` reads the caller's own open tasks and today's meetings and returns
    what to do first and why. It is POST because every call costs a model
    request, and nothing is stored. Any company user may call it: it only ever
    reads the caller's own work, so it needs no lead-view permission.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request):
        body = DailyBriefingRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        ctx = get_tenant_context(request)

        try:
            result = get_daily_briefing_use_case(ctx).execute(
                ctx.user_id,
                body.validated_data["tz"],
            )
        except DailyBriefingUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DailyBriefingError as error:
            return Response(
                {"detail": error.user_message},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DailyBriefingSerializer(result).data,
            status=status.HTTP_200_OK,
        )
