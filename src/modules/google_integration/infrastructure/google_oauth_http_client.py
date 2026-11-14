from urllib.parse import urlencode

import requests
from django.conf import settings

from src.modules.google_integration.application.constants import OAUTH_SCOPES
from src.modules.google_integration.application.dto.oauth import GoogleTokenResponse
from src.modules.google_integration.application.errors import (
    GoogleIntegrationNotConfiguredError,
    GoogleInvalidGrantError,
    GoogleOAuthError,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthHttpClient(GoogleOAuthClient):
    """Plain HTTP calls to Google's OAuth endpoints (no Google SDK)."""

    @staticmethod
    def _setting(name: str) -> str:
        return (getattr(settings, name, "") or "").strip()

    @staticmethod
    def _timeout() -> int:
        return int(getattr(settings, "GOOGLE_API_TIMEOUT", 15))

    def is_configured(self) -> bool:
        return all(
            self._setting(name)
            for name in (
                "GOOGLE_CLIENT_ID",
                "GOOGLE_CLIENT_SECRET",
                "GOOGLE_REDIRECT_URI",
                "GOOGLE_TOKEN_ENCRYPTION_KEY",
            )
        )

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise GoogleIntegrationNotConfiguredError(
                "Google integration is not configured on the server."
            )

    def build_authorization_url(self, state: str, login_hint: str | None = None) -> str:
        self._require_configured()
        params = {
            "client_id": self._setting("GOOGLE_CLIENT_ID"),
            "redirect_uri": self._setting("GOOGLE_REDIRECT_URI"),
            "response_type": "code",
            "scope": " ".join(OAUTH_SCOPES),
            "access_type": "offline",
            # Forces Google to hand out a refresh token on every connect.
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        if login_hint:
            params["login_hint"] = login_hint
        return f"{AUTH_URL}?{urlencode(params)}"

    def _post(self, url: str, data: dict) -> requests.Response:
        try:
            return requests.post(url, data=data, timeout=self._timeout())
        except requests.RequestException as exc:
            raise GoogleOAuthError("Could not reach Google. Please try again.") from exc

    def exchange_code(self, code: str) -> GoogleTokenResponse:
        self._require_configured()
        response = self._post(
            TOKEN_URL,
            {
                "code": code,
                "client_id": self._setting("GOOGLE_CLIENT_ID"),
                "client_secret": self._setting("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": self._setting("GOOGLE_REDIRECT_URI"),
                "grant_type": "authorization_code",
            },
        )
        if response.status_code != 200:
            raise GoogleOAuthError("Google rejected the sign-in. Please try connecting again.")

        body = response.json()
        access_token = body.get("access_token")
        if not access_token:
            raise GoogleOAuthError("Google did not return an access token.")

        return GoogleTokenResponse(
            access_token=access_token,
            refresh_token=body.get("refresh_token"),
            scopes=tuple((body.get("scope") or "").split()),
        )

    def refresh_access_token(self, refresh_token: str) -> str:
        self._require_configured()
        response = self._post(
            TOKEN_URL,
            {
                "refresh_token": refresh_token,
                "client_id": self._setting("GOOGLE_CLIENT_ID"),
                "client_secret": self._setting("GOOGLE_CLIENT_SECRET"),
                "grant_type": "refresh_token",
            },
        )
        if response.status_code != 200:
            try:
                error = response.json().get("error")
            except ValueError:
                error = None
            if error == "invalid_grant":
                raise GoogleInvalidGrantError("Google refresh token is no longer valid.")
            raise GoogleOAuthError("Could not refresh Google access.")

        access_token = response.json().get("access_token")
        if not access_token:
            raise GoogleOAuthError("Google did not return an access token.")
        return access_token

    def fetch_account_email(self, access_token: str) -> str:
        try:
            response = requests.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout(),
            )
        except requests.RequestException as exc:
            raise GoogleOAuthError("Could not reach Google. Please try again.") from exc

        if response.status_code != 200:
            raise GoogleOAuthError("Could not read the Google account email.")
        email = (response.json().get("email") or "").strip()
        if not email:
            raise GoogleOAuthError("Google did not return the account email.")
        return email

    def revoke_token(self, token: str) -> None:
        try:
            requests.post(REVOKE_URL, data={"token": token}, timeout=self._timeout())
        except requests.RequestException:
            pass
