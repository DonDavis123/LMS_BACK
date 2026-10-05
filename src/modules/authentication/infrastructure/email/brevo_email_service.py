import json
import logging
from email.utils import parseaddr
from html import escape
from urllib import error, request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from src.modules.authentication.application.interfaces.email_service import (
    EmailService,
)
from src.modules.authentication.infrastructure.email.reset_link import (
    build_reset_link,
)

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailService(EmailService):
    """Sends email through Brevo's HTTPS API (port 443).

    Hosts such as Render's free tier block outbound SMTP ports
    (25/465/587), so SMTP can never connect there. An HTTPS call is not
    affected. Uses only the standard library — no new dependency.

    DEFAULT_FROM_EMAIL must be a sender verified in Brevo.
    """

    def send_password_reset_email(
        self,
        recipient_email: str,
        reset_token: str,
    ) -> None:
        if not settings.BREVO_API_KEY:
            raise ImproperlyConfigured(
                "BREVO_API_KEY is not set; cannot send email."
            )

        sender_name, sender_email = parseaddr(settings.DEFAULT_FROM_EMAIL or "")
        if not sender_email:
            raise ImproperlyConfigured(
                "DEFAULT_FROM_EMAIL is not set; cannot send email."
            )

        reset_link = build_reset_link(reset_token)
        safe_link = escape(reset_link, quote=True)

        payload = {
            "sender": {
                "name": sender_name or "Lead Management System",
                "email": sender_email,
            },
            "to": [{"email": recipient_email}],
            "subject": "Reset your Lead Management System password",
            "textContent": (
                "You requested to reset your password.\n\n"
                "Use the following link to reset your password:\n\n"
                f"{reset_link}\n\n"
                "This link will expire in 15 minutes.\n\n"
                "If you did not request a password reset, "
                "you can safely ignore this email."
            ),
            "htmlContent": (
                "<p>You requested to reset your password.</p>"
                f'<p><a href="{safe_link}">Reset your password</a></p>'
                "<p>This link will expire in 15 minutes.</p>"
                "<p>If you did not request a password reset, "
                "you can safely ignore this email.</p>"
            ),
        }

        http_request = request.Request(
            BREVO_SEND_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "lms-backend/1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(
                http_request,
                timeout=settings.EMAIL_TIMEOUT,
            ):
                pass
        except error.HTTPError as exc:
            # Brevo explains what is wrong (unverified sender, bad key...).
            detail = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "Brevo rejected the password reset email: %s %s",
                exc.code,
                detail,
            )
            raise
