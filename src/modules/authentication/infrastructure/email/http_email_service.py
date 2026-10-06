import json
import logging
from html import escape
from urllib import error, request
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from src.modules.authentication.application.interfaces.email_service import (
    EmailService,
)
from src.modules.authentication.infrastructure.email.reset_link import (
    build_reset_link,
)

logger = logging.getLogger(__name__)


class HttpEmailService(EmailService):
    """Delivers the password-reset link with a plain HTTP POST.

    The backend does not talk to any email vendor. It POSTs a JSON
    document to EMAIL_HTTP_ENDPOINT (an internal mail relay, an n8n /
    Zapier / Apps Script webhook, ...) and that endpoint delivers it.
    HTTP(S) uses port 80/443, so hosts that block outbound SMTP
    (e.g. Render's free tier) are not affected.

    Request:
        POST {EMAIL_HTTP_ENDPOINT}
        Content-Type: application/json
        Authorization: Bearer {EMAIL_HTTP_TOKEN}   (only when configured)

        {
          "to": "user@example.com",
          "subject": "...",
          "text": "...",
          "html": "...",
          "reset_link": "https://app/reset-password?token=..."
        }

    Any 2xx response is treated as success. Standard library only.
    """

    def send_password_reset_email(
        self,
        recipient_email: str,
        reset_token: str,
    ) -> None:
        endpoint = self._get_endpoint()

        reset_link = build_reset_link(reset_token)
        safe_link = escape(reset_link, quote=True)

        payload = {
            "to": recipient_email,
            "subject": "Reset your Lead Management System password",
            "text": (
                "You requested to reset your password.\n\n"
                "Use the following link to reset your password:\n\n"
                f"{reset_link}\n\n"
                "This link will expire in 15 minutes.\n\n"
                "If you did not request a password reset, "
                "you can safely ignore this email."
            ),
            "html": (
                "<p>You requested to reset your password.</p>"
                f'<p><a href="{safe_link}">Reset your password</a></p>'
                "<p>This link will expire in 15 minutes.</p>"
                "<p>If you did not request a password reset, "
                "you can safely ignore this email.</p>"
            ),
            "reset_link": reset_link,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lms-backend/1.0",
        }

        if settings.EMAIL_HTTP_TOKEN:
            headers["Authorization"] = f"Bearer {settings.EMAIL_HTTP_TOKEN}"

        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(
                http_request,
                timeout=settings.EMAIL_TIMEOUT,
            ) as response:
                body = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "Mail endpoint rejected the password reset request: %s %s",
                exc.code,
                detail,
            )
            raise

        self._raise_if_relay_reported_failure(body)

    @staticmethod
    def _raise_if_relay_reported_failure(body: str) -> None:
        """Some relays (e.g. Google Apps Script) answer HTTP 200 even when
        sending failed and report it as {"ok": false, "error": "..."}.
        Non-JSON or JSON without an "ok" flag is treated as success.
        """
        try:
            data = json.loads(body)
        except (TypeError, ValueError):
            return

        if isinstance(data, dict) and data.get("ok") is False:
            logger.error(
                "Mail endpoint reported a failure: %s",
                data.get("error"),
            )
            raise RuntimeError(
                f"Mail endpoint reported a failure: {data.get('error')}"
            )

    @staticmethod
    def _get_endpoint() -> str:
        endpoint = (settings.EMAIL_HTTP_ENDPOINT or "").strip()

        if not endpoint:
            raise ImproperlyConfigured(
                "EMAIL_HTTP_ENDPOINT is not set; cannot send email."
            )

        if urlparse(endpoint).scheme not in {"http", "https"}:
            raise ImproperlyConfigured(
                "EMAIL_HTTP_ENDPOINT must start with http:// or https://."
            )

        return endpoint
