import unittest
from datetime import datetime, timezone
from uuid import uuid4

from src.modules.google_integration.application.dto.oauth import (
    GoogleOAuthState,
    GoogleTokenResponse,
)
from src.modules.google_integration.application.errors import (
    GoogleInvalidGrantError,
    GoogleNotConnectedError,
    GoogleOAuthError,
    GoogleOAuthStateError,
)
from src.modules.google_integration.application.constants import CALENDAR_EVENTS_SCOPE
from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)
from src.modules.google_integration.application.interfaces.oauth_state_signer import (
    OAuthStateSigner,
)
from src.modules.google_integration.application.interfaces.token_cipher import TokenCipher
from src.modules.google_integration.application.services.google_access_token_service import (
    GoogleAccessTokenService,
)
from src.modules.google_integration.application.use_cases.complete_google_connect import (
    CompleteGoogleConnectUseCase,
)
from src.modules.google_integration.application.use_cases.disconnect_google import (
    DisconnectGoogleUseCase,
)
from src.modules.google_integration.application.use_cases.get_google_connection_status import (
    GetGoogleConnectionStatusUseCase,
)
from src.modules.google_integration.application.use_cases.start_google_connect import (
    StartGoogleConnectUseCase,
)
from src.modules.google_integration.domain.entities.google_connection import GoogleConnection
from src.modules.google_integration.domain.enums.google_connection_status import (
    GoogleConnectionStatus,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class FakeRepo(GoogleConnectionRepository):
    def __init__(self):
        self.items = {}

    def get_by_user_id(self, user_id):
        return self.items.get(user_id)

    def save(self, connection):
        self.items[connection.user_id] = connection
        return connection

    def delete_by_user_id(self, user_id):
        return self.items.pop(user_id, None) is not None


class FakeCipher(TokenCipher):
    def encrypt(self, plain_text):
        return f"enc:{plain_text}"

    def decrypt(self, cipher_text):
        return cipher_text.removeprefix("enc:")


class FakeSigner(OAuthStateSigner):
    def sign(self, user_id, company_id):
        return f"{user_id}|{company_id}"

    def verify(self, state):
        raise GoogleOAuthStateError("invalid")


class FakeOAuth(GoogleOAuthClient):
    def __init__(self):
        self.tokens = GoogleTokenResponse("access", "refresh", ("openid", "email", CALENDAR_EVENTS_SCOPE))
        self.invalid_grant = False
        self.revoked = []
        self.login_hints = []

    def is_configured(self):
        return True

    def build_authorization_url(self, state, login_hint=None):
        self.login_hints.append(login_hint)
        return f"https://accounts.example/auth?state={state}"

    def exchange_code(self, code):
        return self.tokens

    def refresh_access_token(self, refresh_token):
        if self.invalid_grant:
            raise GoogleInvalidGrantError("dead")
        return f"access-for-{refresh_token}"

    def fetch_account_email(self, access_token):
        return "Person@Gmail.com"

    def revoke_token(self, token):
        self.revoked.append(token)


class FakeUsers:
    def __init__(self, *users):
        self.users = {u.id: u for u in users}

    def get_by_id(self, user_id):
        return self.users.get(user_id)


def make_user(google_email=None, active=True):
    now = datetime.now(timezone.utc)
    return User(uuid4(), "U", "u@example.com", UserRole.ADMIN, active, now, now, google_email=google_email)


class GoogleIntegrationApplicationTests(unittest.TestCase):
    def setUp(self):
        self.user = make_user("hint@gmail.com")
        self.company_id = uuid4()
        self.repo = FakeRepo()
        self.oauth = FakeOAuth()
        self.cipher = FakeCipher()

    def complete(self):
        return CompleteGoogleConnectUseCase(self.repo, FakeUsers(self.user), self.oauth, self.cipher)

    def state(self):
        return GoogleOAuthState(self.user.id, self.company_id)

    def test_start_uses_saved_google_email_as_login_hint(self):
        url = StartGoogleConnectUseCase(FakeUsers(self.user), self.oauth, FakeSigner()).execute(
            self.user.id, self.company_id
        )

        self.assertIn("state=", url)
        self.assertEqual(self.oauth.login_hints, ["hint@gmail.com"])

    def test_start_rejects_inactive_user(self):
        inactive = make_user(active=False)

        with self.assertRaises(ValueError):
            StartGoogleConnectUseCase(FakeUsers(inactive), self.oauth, FakeSigner()).execute(
                inactive.id, self.company_id
            )

    def test_complete_stores_encrypted_token_and_normalised_email(self):
        connection = self.complete().execute("code", self.state())

        self.assertEqual(connection.refresh_token_encrypted, "enc:refresh")
        self.assertNotEqual(connection.refresh_token_encrypted, "refresh")
        self.assertEqual(connection.google_email, "person@gmail.com")
        self.assertTrue(connection.is_connected)
        self.assertIs(self.repo.items[self.user.id], connection)

    def test_complete_reconnect_replaces_revoked_connection(self):
        self.complete().execute("code", self.state())
        self.repo.items[self.user.id].mark_revoked()

        connection = self.complete().execute("code", self.state())

        self.assertTrue(connection.is_connected)
        self.assertIsNone(connection.revoked_at)
        self.assertEqual(len(self.repo.items), 1)

    def test_complete_requires_calendar_scope(self):
        self.oauth.tokens = GoogleTokenResponse("access", "refresh", ("openid", "email"))

        with self.assertRaises(GoogleOAuthError):
            self.complete().execute("code", self.state())

        self.assertEqual(self.repo.items, {})

    def test_complete_requires_refresh_token(self):
        self.oauth.tokens = GoogleTokenResponse("access", None, ("openid", CALENDAR_EVENTS_SCOPE))

        with self.assertRaises(GoogleOAuthError):
            self.complete().execute("code", self.state())

    def test_complete_requires_code_and_active_user(self):
        with self.assertRaises(GoogleOAuthError):
            self.complete().execute("", self.state())

        with self.assertRaises(GoogleOAuthStateError):
            self.complete().execute("code", GoogleOAuthState(uuid4(), self.company_id))

    def test_access_token_service_refreshes_with_decrypted_token(self):
        self.complete().execute("code", self.state())
        service = GoogleAccessTokenService(self.repo, self.oauth, self.cipher)

        token = service.get_access_token(self.user.id)

        self.assertEqual(token.access_token, "access-for-refresh")
        self.assertEqual(service.get_connected_email(self.user.id), "person@gmail.com")

    def test_access_token_service_not_connected(self):
        service = GoogleAccessTokenService(self.repo, self.oauth, self.cipher)

        self.assertIsNone(service.get_connected_email(self.user.id))
        with self.assertRaises(GoogleNotConnectedError):
            service.get_access_token(self.user.id)

    def test_invalid_grant_marks_connection_revoked(self):
        self.complete().execute("code", self.state())
        self.oauth.invalid_grant = True
        service = GoogleAccessTokenService(self.repo, self.oauth, self.cipher)

        with self.assertRaises(GoogleNotConnectedError):
            service.get_access_token(self.user.id)

        self.assertEqual(self.repo.items[self.user.id].status, GoogleConnectionStatus.REVOKED)
        self.assertIsNone(service.get_connected_email(self.user.id))

    def test_status(self):
        use_case = GetGoogleConnectionStatusUseCase(self.repo, self.oauth)
        self.assertFalse(use_case.execute(self.user.id).connected)

        self.complete().execute("code", self.state())
        result = use_case.execute(self.user.id)

        self.assertTrue(result.connected)
        self.assertTrue(result.configured)
        self.assertEqual(result.google_email, "person@gmail.com")

    def test_disconnect_revokes_and_deletes(self):
        self.complete().execute("code", self.state())

        removed = DisconnectGoogleUseCase(self.repo, self.oauth, self.cipher).execute(self.user.id)

        self.assertTrue(removed)
        self.assertEqual(self.oauth.revoked, ["refresh"])
        self.assertEqual(self.repo.items, {})

    def test_disconnect_without_connection(self):
        self.assertFalse(DisconnectGoogleUseCase(self.repo, self.oauth, self.cipher).execute(uuid4()))


class GoogleConnectionEntityTests(unittest.TestCase):
    def test_create_requires_email_and_token(self):
        with self.assertRaises(ValueError):
            GoogleConnection.create(uuid4(), uuid4(), " ", "enc", "scope")
        with self.assertRaises(ValueError):
            GoogleConnection.create(uuid4(), uuid4(), "a@b.com", "", "scope")


if __name__ == "__main__":
    unittest.main()
