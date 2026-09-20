from src.modules.authentication.application.use_cases.login_user import (
    LoginUserUseCase,
)

from src.modules.authentication.application.use_cases.refreshtoken import (
    RefreshTokenUseCase,
)

from src.modules.authentication.application.use_cases.logout_user import (
    LogoutUserUseCase,
)

from src.modules.authentication.application.use_cases.forgot_password import (
    ForgotPasswordUseCase,
)

from src.modules.authentication.application.use_cases.reset_password import (
    ResetPasswordUseCase,
)

from src.modules.authentication.infrastructure.persistence.django_user_repository import (
    DjangoUserRepository,
)

from src.modules.authentication.infrastructure.security.django_password_hasher import (
    DjangoPasswordHasher,
)

from src.modules.authentication.infrastructure.security.jwt_token_service import (
    JWTTokenService,
)

from src.modules.authentication.infrastructure.security.password_reset import (
    DjangoPasswordResetTokenService,
)

from src.modules.authentication.infrastructure.email import (
    DjangoEmailService,
)


def get_login_user_use_case() -> LoginUserUseCase:
    user_repository = DjangoUserRepository()
    password_hasher = DjangoPasswordHasher()
    token_service = JWTTokenService()

    return LoginUserUseCase(
        user_repository=user_repository,
        password_hasher=password_hasher,
        token_service=token_service,
    )


def get_refresh_token_use_case() -> RefreshTokenUseCase:
    token_service = JWTTokenService()

    return RefreshTokenUseCase(
        token_service=token_service,
    )


def get_logout_user_use_case() -> LogoutUserUseCase:
    token_service = JWTTokenService()

    return LogoutUserUseCase(
        token_service=token_service,
    )


def get_forgot_password_use_case() -> ForgotPasswordUseCase:
    user_repository = DjangoUserRepository()
    password_reset_token_service = DjangoPasswordResetTokenService()
    email_service = DjangoEmailService()

    return ForgotPasswordUseCase(
        user_repository=user_repository,
        password_reset_token_service=password_reset_token_service,
        email_service=email_service,
    )


def get_reset_password_use_case() -> ResetPasswordUseCase:
    user_repository = DjangoUserRepository()
    password_reset_token_service = DjangoPasswordResetTokenService()
    password_hasher = DjangoPasswordHasher()

    return ResetPasswordUseCase(
        user_repository=user_repository,
        password_reset_token_service=password_reset_token_service,
        password_hasher=password_hasher,
    )
