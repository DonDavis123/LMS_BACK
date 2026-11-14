import time
from datetime import timezone
from uuid import UUID

import requests
from django.conf import settings

from src.modules.google_integration.application.errors import (
    GoogleIntegrationNotConfiguredError,
    GoogleNotConnectedError,
    GoogleOAuthError,
)
from src.modules.google_integration.application.services.google_access_token_service import (
    GoogleAccessTokenService,
)
from src.modules.meetings.application.interfaces.video_conference_provider import (
    ConferenceEvent,
    ConferenceEventResult,
    VideoConferenceError,
    VideoConferenceNotConnectedError,
    VideoConferenceProvider,
)
from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider

EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# How often to re-read an event whose Meet link Google is still generating.
_LINK_POLL_ATTEMPTS = 3
_LINK_POLL_DELAY_SECONDS = 1.0


class GoogleMeetProvider(VideoConferenceProvider):
    """Google Calendar adapter: one event per meeting, with a Meet link.

    ``sendUpdates=all`` makes Google email the invite, every later update and
    the cancellation to the attendees, from the organizer's own Gmail.
    """

    def __init__(self, access_token_service: GoogleAccessTokenService):
        self.access_token_service = access_token_service

    @property
    def provider_type(self) -> ConferenceProvider:
        return ConferenceProvider.GOOGLE_MEET

    def get_connected_account_email(self, user_id: UUID) -> str | None:
        return self.access_token_service.get_connected_email(user_id)

    # ------------------------------------------------------------------
    # Port methods
    # ------------------------------------------------------------------

    def create_event(self, owner_user_id: UUID, event: ConferenceEvent) -> ConferenceEventResult:
        headers = self._headers(owner_user_id)
        body = self._event_body(event, creating=True)
        body["id"] = event.client_event_id
        body["conferenceData"] = {
            "createRequest": {
                "requestId": event.client_event_id,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

        response = self._request(
            "POST",
            EVENTS_URL,
            headers,
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json=body,
        )

        if response.status_code == 409:
            # Same client event id already exists: an earlier attempt succeeded
            # but its response was lost. Reuse that event instead of failing.
            existing = self._request("GET", f"{EVENTS_URL}/{event.client_event_id}", headers)
            self._raise_for_error(existing)
            data = existing.json()
            if data.get("status") == "cancelled":
                raise VideoConferenceError("The Google event for this meeting was deleted.")
        else:
            self._raise_for_error(response)
            data = response.json()

        event_id = data.get("id") or event.client_event_id
        link = self._extract_meet_link(data)

        attempts = 0
        while not link and attempts < _LINK_POLL_ATTEMPTS:
            # Meet links are sometimes generated a moment after the insert.
            time.sleep(_LINK_POLL_DELAY_SECONDS)
            polled = self._request("GET", f"{EVENTS_URL}/{event_id}", headers)
            self._raise_for_error(polled)
            link = self._extract_meet_link(polled.json())
            attempts += 1

        if not link:
            raise VideoConferenceError("Google did not return a Meet link for the event.")

        return ConferenceEventResult(event_id=event_id, meet_link=link)

    def update_event(self, owner_user_id: UUID, event_id: str, event: ConferenceEvent) -> None:
        headers = self._headers(owner_user_id)
        response = self._request(
            "PATCH",
            f"{EVENTS_URL}/{event_id}",
            headers,
            params={"conferenceDataVersion": 1, "sendUpdates": "all"},
            json=self._event_body(event, creating=False),
        )
        self._raise_for_error(response)

    def cancel_event(self, owner_user_id: UUID, event_id: str) -> None:
        headers = self._headers(owner_user_id)
        response = self._request(
            "DELETE",
            f"{EVENTS_URL}/{event_id}",
            headers,
            params={"sendUpdates": "all"},
        )
        # Already gone (404) or deleted (410) counts as cancelled.
        if response.status_code in (404, 410):
            return
        self._raise_for_error(response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self, owner_user_id: UUID) -> dict:
        try:
            token = self.access_token_service.get_access_token(owner_user_id)
        except GoogleNotConnectedError as exc:
            raise VideoConferenceNotConnectedError(str(exc)) from exc
        except (GoogleOAuthError, GoogleIntegrationNotConfiguredError) as exc:
            raise VideoConferenceError(
                str(exc) or "Google integration is not available."
            ) from exc
        return {"Authorization": f"Bearer {token.access_token}"}

    @staticmethod
    def _timeout() -> int:
        return int(getattr(settings, "GOOGLE_API_TIMEOUT", 15))

    def _request(self, method: str, url: str, headers: dict, **kwargs) -> requests.Response:
        try:
            return requests.request(
                method, url, headers=headers, timeout=self._timeout(), **kwargs
            )
        except requests.RequestException as exc:
            raise VideoConferenceError("Could not reach Google Calendar.") from exc

    @staticmethod
    def _event_body(event: ConferenceEvent, creating: bool) -> dict:
        def moment(value):
            return {
                "dateTime": value.astimezone(timezone.utc).isoformat(),
                "timeZone": "UTC",
            }

        body = {
            "summary": event.title,
            "start": moment(event.start_at),
            "end": moment(event.end_at),
            "attendees": [{"email": email} for email in event.attendee_emails],
        }
        # On create, omit empty values. On patch send them, so a cleared
        # description/location is cleared in Google as well.
        if event.description or not creating:
            body["description"] = event.description or ""
        if event.location or not creating:
            body["location"] = event.location or ""
        return body

    @staticmethod
    def _extract_meet_link(data: dict) -> str | None:
        link = data.get("hangoutLink")
        if link:
            return link
        for entry in (data.get("conferenceData") or {}).get("entryPoints") or []:
            if entry.get("entryPointType") == "video" and entry.get("uri"):
                return entry["uri"]
        return None

    @staticmethod
    def _raise_for_error(response: requests.Response) -> None:
        if response.status_code < 400:
            return

        message = ""
        try:
            message = (response.json().get("error") or {}).get("message") or ""
        except (ValueError, AttributeError):
            pass
        detail = f": {message}" if message else ""
        raise VideoConferenceError(
            f"Google Calendar error ({response.status_code}){detail}"[:500]
        )
