from src.modules.authentication.application.interfaces import (
    EmailService,
    PasswordResetTokenService,
    UserRepository,
)


class ForgotPasswordUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        password_reset_token_service: PasswordResetTokenService,
        email_service: EmailService,
    ):
        self.user_repository = user_repository
        self.password_reset_token_service = (
            password_reset_token_service
        )
        self.email_service = email_service

    def execute(self, email: str) -> None:
        user = self.user_repository.get_by_email(email)

        # Do not reveal whether the email exists.
        if user is None:
            return

        if not user.is_active:
            return

        reset_token = (
            self.password_reset_token_service.generate_token(
                user_id=user.id,
            )
        )

        self.email_service.send_password_reset_email(
            recipient_email=user.email,
            reset_token=reset_token,
        )