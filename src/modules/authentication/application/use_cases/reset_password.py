from src.modules.authentication.application.dto.reset_password import (
    ResetPasswordDTO,
)
from src.modules.authentication.application.interfaces import (
    PasswordHasher,
    PasswordResetTokenService,
    UserRepository,
)


class ResetPasswordUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        password_reset_token_service: PasswordResetTokenService,
        password_hasher: PasswordHasher,
    ):
        self.user_repository = user_repository
        self.password_reset_token_service = (
            password_reset_token_service
        )
        self.password_hasher = password_hasher

    def execute(self, data: ResetPasswordDTO) -> None:
        user_id = self.password_reset_token_service.validate_token(
            data.token,
        )

        if user_id is None:
            raise ValueError(
                "Invalid or expired password reset token."
            )

        user = self.user_repository.get_by_id(user_id)

        if user is None:
            raise ValueError("User not found.")

        if not user.is_active:
            raise ValueError("User account is inactive.")

        hashed_password = self.password_hasher.hash(
            data.new_password,
        )

        user.password = hashed_password

        self.user_repository.save(user)

        self.password_reset_token_service.consume_token(
            data.token,
        )