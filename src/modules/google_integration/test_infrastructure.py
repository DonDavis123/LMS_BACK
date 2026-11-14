from unittest import mock
from uuid import uuid4

from django.core import signing
from django.test import SimpleTestCase, override_settings

from cryptography.fernet import Fernet

from src.modules.google_integration.application.errors import (
    GoogleIntegrationNotConfiguredError,
    GoogleInvalidGrantError,
    GoogleOAuthError,
    GoogleOAuthStateError,
)
from src.modules.google_integration.infrastructure.fernet_token_cipher import FernetTokenCipher
from src.modules.google_integration.infrastructure.google_oauth_http_client import (
    GoogleOAuthHttpClient,
)
from src.modules.google_integration.infrastructure.signed_oauth_state import (
    SignedOAuthStateSigner,
)

KEY = Fernet.generate_key().decode()

GOOGLE_SETTINGS = dict(
    GOOGLE_CLIENT_ID="client-id",
    GOOGLE_CLIENT_SECRET="client-secret",
    GOOGLE_REDIRECT_URI="https://api.example.com/api/integrations/google/callback/",
    GOOGLE_TOKEN_ENCRYPTION_KEY=KEY,
)


def response(status_code=200, body=None):
    fake = mock.Mock()
    fake.status_code = status_code
    fake.json.return_value = body or {}
    return fake


class SignedOAuthStateTests(SimpleTestCase):
    def test_roundtrip(self):
        signer = SignedOAuthStateSigner()
        user_id, company_id = uuid4(), uuid4()

        state = signer.verify(signer.sign(user_id, company_id))

        self.assertEqual((state.user_id, state.company_id), (user_id, company_id))

    def test_tampered_state_is_rejected(self):
        signer = SignedOAuthStateSigner()
        state = signer.sign(uuid4(), uuid4())

        with self.assertRaises(GoogleOAuthStateError):
            signer.verify(state[:-2] + ("AA" if not state.endswith("AA") else "BB"))

    def test_foreign_salt_is_rejected(self):
        forged = signing.dumps({"u": str(uuid4()), "c": str(uuid4())}, salt="other")

        with self.assertRaises(GoogleOAuthStateError):
            SignedOAuthStateSigner().verify(forged)

    def test_empty_and_garbage_are_rejected(self):
        signer = SignedOAuthStateSigner()
        for value in ("", "garbage", "a:b:c"):
            with self.assertRaises(GoogleOAuthStateError):
                signer.verify(value)

    @override_settings(GOOGLE_OAUTH_STATE_MAX_AGE=600)
    def test_expired_state_is_rejected(self):
        signer = SignedOAuthStateSigner()
        state = signer.sign(uuid4(), uuid4())

        with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + 601):
            with self.assertRaises(GoogleOAuthStateError):
                signer.verify(state)


class FernetTokenCipherTests(SimpleTestCase):
    @override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY=KEY)
    def test_roundtrip_and_ciphertext_differs(self):
        cipher = FernetTokenCipher()
        encrypted = cipher.encrypt("refresh-token")

        self.assertNotIn("refresh-token", encrypted)
        self.assertEqual(cipher.decrypt(encrypted), "refresh-token")

    @override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY="")
    def test_missing_key(self):
        with self.assertRaises(GoogleIntegrationNotConfiguredError):
            FernetTokenCipher().encrypt("x")

    @override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY="not-a-key")
    def test_invalid_key(self):
        with self.assertRaises(GoogleIntegrationNotConfiguredError):
            FernetTokenCipher().encrypt("x")

    def test_wrong_key_cannot_decrypt(self):
        with override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY=KEY):
            encrypted = FernetTokenCipher().encrypt("x")
        with override_settings(GOOGLE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(GoogleIntegrationNotConfiguredError):
                FernetTokenCipher().decrypt(encrypted)


@override_settings(**GOOGLE_SETTINGS)
class GoogleOAuthHttpClientTests(SimpleTestCase):
    def setUp(self):
        self.client = GoogleOAuthHttpClient()

    def test_authorization_url(self):
        url = self.client.build_authorization_url("the-state", "me@gmail.com")

        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))
        for part in (
            "client_id=client-id",
            "access_type=offline",
            "prompt=consent",
            "state=the-state",
            "login_hint=me%40gmail.com",
            "calendar.events",
        ):
            self.assertIn(part, url)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_not_configured(self):
        self.assertFalse(self.client.is_configured())
        with self.assertRaises(GoogleIntegrationNotConfiguredError):
            self.client.build_authorization_url("s")

    @mock.patch("src.modules.google_integration.infrastructure.google_oauth_http_client.requests.post")
    def test_exchange_code(self, post):
        post.return_value = response(
            body={"access_token": "a", "refresh_token": "r", "scope": "openid email calendar"}
        )

        tokens = self.client.exchange_code("code")

        self.assertEqual((tokens.access_token, tokens.refresh_token), ("a", "r"))
        self.assertEqual(tokens.scopes, ("openid", "email", "calendar"))
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "authorization_code")

    @mock.patch("src.modules.google_integration.infrastructure.google_oauth_http_client.requests.post")
    def test_exchange_code_failure(self, post):
        post.return_value = response(400, {"error": "invalid_request"})

        with self.assertRaises(GoogleOAuthError):
            self.client.exchange_code("code")

    @mock.patch("src.modules.google_integration.infrastructure.google_oauth_http_client.requests.post")
    def test_refresh_invalid_grant(self, post):
        post.return_value = response(400, {"error": "invalid_grant"})

        with self.assertRaises(GoogleInvalidGrantError):
            self.client.refresh_access_token("r")

    @mock.patch("src.modules.google_integration.infrastructure.google_oauth_http_client.requests.post")
    def test_refresh_success(self, post):
        post.return_value = response(body={"access_token": "fresh"})

        self.assertEqual(self.client.refresh_access_token("r"), "fresh")
