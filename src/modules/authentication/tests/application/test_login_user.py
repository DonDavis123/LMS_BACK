from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from src.modules.authentication.domain.exceptions import (
    InvalidCredentialsError,
    InactiveUserError,
)

from src.modules.authentication.application.use_cases.login_user import (
    LoginUserUseCase,
)


class LoginUserUseCaseTests(TestCase):

    def test_login_success(self):
        user = SimpleNamespace(
            id="user-123",
            email="dondavisdon2@gmail.com",
            password="hashed-password",
            is_active=True,
        )

        user_repository = Mock()
        user_repository.get_by_email.return_value = user

        password_hasher = Mock()
        password_hasher.verify.return_value = True

        token_service = Mock()
        token_service.generate_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        }

        use_case = LoginUserUseCase(
            user_repository=user_repository,
            password_hasher=password_hasher,
            token_service=token_service,
        )

        result = use_case.execute(
            email="dondavisdon2@gmail.com",
            password="correct-password",
        )

        self.assertEqual(result.access_token, "access-token")
        self.assertEqual(result.refresh_token, "refresh-token")
        self.assertEqual(result.user, user)

        user_repository.get_by_email.assert_called_once_with(
            "dondavisdon2@gmail.com"
        )

        password_hasher.verify.assert_called_once_with(
            password="correct-password",
            hashed_password="hashed-password",
        )

        token_service.generate_tokens.assert_called_once_with(user)
    def test_login_fails_when_user_does_not_exist(self):
        user_repository = Mock()
        user_repository.get_by_email.return_value = None

        password_hasher = Mock()
        token_service = Mock()

        use_case = LoginUserUseCase(
            user_repository=user_repository,
            password_hasher=password_hasher,
            token_service=token_service,
        )

        with self.assertRaises(InvalidCredentialsError):
            use_case.execute(
                email="unknown@example.com",
                password="password123",
            )

        password_hasher.verify.assert_not_called()
        token_service.generate_tokens.assert_not_called()
    def test_login_fails_with_wrong_password(self):
        user = SimpleNamespace(
            id="user-123",
            email="dondavisdon2@gmail.com",
            password="hashed-password",
            is_active=True,
        )

        user_repository = Mock()
        user_repository.get_by_email.return_value = user

        password_hasher = Mock()
        password_hasher.verify.return_value = False

        token_service = Mock()

        use_case = LoginUserUseCase(
            user_repository=user_repository,
            password_hasher=password_hasher,
            token_service=token_service,
        )

        with self.assertRaises(InvalidCredentialsError):
            use_case.execute(
                email="dondavisdon2@gmail.com",
                password="wrong-password",
            )

        token_service.generate_tokens.assert_not_called() 
    def test_login_fails_when_user_is_inactive(self):
        user = SimpleNamespace(
            id="user-123",
            email="dondavisdon2@gmail.com",
            password="hashed-password",
            is_active=False,
        )

        user_repository = Mock()
        user_repository.get_by_email.return_value = user

        password_hasher = Mock()
        token_service = Mock()

        use_case = LoginUserUseCase(
            user_repository=user_repository,
            password_hasher=password_hasher,
            token_service=token_service,
        )

        with self.assertRaises(InactiveUserError):
            use_case.execute(
                email="dondavisdon2@gmail.com",
                password="correct-password",
            )

        password_hasher.verify.assert_not_called()
        token_service.generate_tokens.assert_not_called()       