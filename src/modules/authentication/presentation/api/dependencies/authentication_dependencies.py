from src.modules.authentication.application.use_cases.login_user import (
    LoginUserUseCase,
)
from src.modules.authentication.application.use_cases.refreshtoken import (
    RefreshTokenUseCase,
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