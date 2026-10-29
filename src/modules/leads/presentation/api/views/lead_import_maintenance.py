import hmac

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.infrastructure.lead_import_maintenance import run_maintenance

SECRET_HEADER = "X-Import-Secret"


def _not_found() -> HttpResponse:
    """A plain 404 with an empty body: nothing reveals the endpoint exists."""
    return HttpResponse(status=404)


def _secret_matches(provided: str | None) -> bool:
    configured = getattr(settings, "LEAD_IMPORT_CRON_SECRET", "") or ""
    if not configured or not provided:
        return False
    return hmac.compare_digest(
        provided.encode("utf-8"), configured.encode("utf-8")
    )


class ImportMaintenanceView(APIView):
    """Scheduler-only housekeeping for lead imports (see lead_import_maintenance).

    Not protected by a login: the secret header is the only protection, so a
    missing login must not answer 401. Anything wrong answers an empty 404,
    including a wrong HTTP method or an odd Accept header.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []
    http_method_names = ["get", "post"]

    def http_method_not_allowed(self, request, *args, **kwargs):
        return _not_found()

    def perform_content_negotiation(self, request, force=False):
        # Never answer 406; the cron tool's Accept header is not our business.
        return super().perform_content_negotiation(request, force=True)

    def get(self, request):
        return self._run(request)

    def post(self, request):
        return self._run(request)

    def _run(self, request):
        if not _secret_matches(request.headers.get(SECRET_HEADER)):
            return _not_found()
        return Response(run_maintenance(), status=status.HTTP_200_OK)
