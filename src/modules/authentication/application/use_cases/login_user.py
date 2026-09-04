from dataclasses import dataclass

from src.modules.authentication.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.authentication.application.interfaces.password_hasher import (
    PasswordHasher,
)
from src.modules.authentication.application.interfaces.token_service import (
    TokenService,
)
from src.modules.authentication.domain.exceptions import (
    InvalidCredentialsError,
    InactiveUserError,
)


@dataclass
class LoginResult:
    access_token: str
    refresh_token: str
    user: object


class LoginUserUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ):
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.token_service = token_service

    def execute(
        self,
        email: str,
        password: str,
    ) -> LoginResult:

        user = self.user_repository.get_by_email(email)

        if user is None:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        password_valid = self.password_hasher.verify(
            password=password,
            hashed_password=user.password,
        )

        if not password_valid:
            raise InvalidCredentialsError()

        tokens = self.token_service.generate_tokens(user)

        return LoginResult(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=user,
        )