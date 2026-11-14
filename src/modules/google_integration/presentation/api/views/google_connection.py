from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.google_integration.application.errors import (
    GoogleIntegrationNotConfiguredError,
)
from src.modules.google_integration.presentation.api.dependencies.google_dependencies import (
    get_complete_google_connect_use_case,
    get_disconnect_google_use_case,
    get_google_connection_status_use_case,
    get_start_google_connect_use_case,
    get_state_signer,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.google_connection import GoogleConnectionStatusSerializer

NOT_CONFIGURED_MESSAGE = "Google integration is not configured on the server."


class GoogleConnectionStatusView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        ctx = get_tenant_context(request)
        result = get_google_connection_status_use_case(ctx).execute(ctx.user_id)
        return Response(
            GoogleConnectionStatusSerializer(result).data,
            status=status.HTTP_200_OK,
        )


class GoogleConnectStartView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request):
        ctx = get_tenant_context(request)
        try:
            url = get_start_google_connect_use_case(ctx).execute(ctx.user_id, ctx.company_id)
        except GoogleIntegrationNotConfiguredError:
            return Response(
                {"detail": NOT_CONFIGURED_MESSAGE},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"authorization_url": url}, status=status.HTTP_200_OK)


class GoogleConnectCallbackView(APIView):
    """Google redirects the browser here after consent.

    There is no JWT on this request. The signed, expiring ``state`` created by
    the connect endpoint identifies the user and company instead. The browser
    is then sent back to the frontend with ``?status=connected|error``.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        error = request.query_params.get("error")
        if error:
            return self._redirect("error", "Google sign-in was cancelled or denied.")

        try:
            state = get_state_signer().verify(request.query_params.get("state", ""))
            use_case = get_complete_google_connect_use_case(state.company_id)
            use_case.execute(request.query_params.get("code", ""), state)
        except GoogleIntegrationNotConfiguredError:
            return self._redirect("error", NOT_CONFIGURED_MESSAGE)
        except ValueError as exc:
            # State/OAuth errors carry curated, user-safe messages.
            return self._redirect("error", str(exc))

        return self._redirect("connected")

    @staticmethod
    def _redirect(result: str, message: str | None = None):
        base_url = (getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
        if not base_url:
            payload = {"status": result}
            if message:
                payload["detail"] = message
            code = status.HTTP_200_OK if result == "connected" else status.HTTP_400_BAD_REQUEST
            return Response(payload, status=code)

        path = getattr(
            settings, "GOOGLE_FRONTEND_RETURN_PATH", "/integrations/google/callback"
        )
        params = {"status": result}
        if message:
            params["message"] = message
        return HttpResponseRedirect(f"{base_url}{path}?{urlencode(params)}")


class GoogleDisconnectView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def delete(self, request):
        ctx = get_tenant_context(request)
        get_disconnect_google_use_case(ctx).execute(ctx.user_id)
        return Response(
            {"message": "Google account disconnected."},
            status=status.HTTP_200_OK,
        )
