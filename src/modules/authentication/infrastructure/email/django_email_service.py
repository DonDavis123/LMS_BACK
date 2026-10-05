from django.conf import settings
from django.core.mail import send_mail

from src.modules.authentication.application.interfaces.email_service import (
    EmailService,
)
from src.modules.authentication.infrastructure.email.reset_link import (
    build_reset_link,
)


class DjangoEmailService(EmailService):

    def send_password_reset_email(
        self,
        recipient_email: str,
        reset_token: str,
    ) -> None:

        reset_link = build_reset_link(reset_token)

        send_mail(
            subject="Reset your Lead Management System password",
            message=(
                "You requested to reset your password.\n\n"
                f"Use the following link to reset your password:\n\n"
                f"{reset_link}\n\n"
                "This link will expire in 15 minutes.\n\n"
                "If you did not request a password reset, "
                "you can safely ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )