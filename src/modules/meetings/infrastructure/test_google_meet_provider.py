import unittest
from datetime import datetime, timezone
from unittest import mock
from uuid import uuid4

from src.modules.google_integration.application.dto.oauth import GoogleAccessToken
from src.modules.google_integration.application.errors import GoogleNotConnectedError
from src.modules.meetings.application.interfaces.video_conference_provider import (
    ConferenceEvent,
    VideoConferenceError,
    VideoConferenceNotConnectedError,
)
from src.modules.meetings.infrastructure import google_meet_provider
from src.modules.meetings.infrastructure.google_meet_provider import GoogleMeetProvider

REQUEST = "src.modules.meetings.infrastructure.google_meet_provider.requests.request"


def response(status_code=200, body=None):
    fake = mock.Mock()
    fake.status_code = status_code
    fake.json.return_value = body if body is not None else {}
    return fake


class FakeTokenService:
    def __init__(self, connected=True):
        self.connected = connected

    def get_connected_email(self, user_id):
        return "host@gmail.com" if self.connected else None

    def get_access_token(self, user_id):
        if not self.connected:
            raise GoogleNotConnectedError("not connected")
        return GoogleAccessToken("token", "host@gmail.com")


def make_event(**kw):
    data = dict(
        title="Demo",
        description="About the demo",
        location=None,
        start_at=datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc),
        attendee_emails=("a@example.com",),
        client_event_id="abc123",
    )
    data.update(kw)
    return ConferenceEvent(**data)


class GoogleMeetProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = GoogleMeetProvider(FakeTokenService())
        self.owner = uuid4()
        patcher = mock.patch.object(google_meet_provider.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    @mock.patch(REQUEST)
    def test_create_sends_invites_and_requests_meet(self, request):
        request.return_value = response(body={"id": "abc123", "hangoutLink": "https://meet.google.com/x"})

        result = self.provider.create_event(self.owner, make_event())

        self.assertEqual((result.event_id, result.meet_link), ("abc123", "https://meet.google.com/x"))
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(kwargs["params"], {"conferenceDataVersion": 1, "sendUpdates": "all"})
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer token"})
        body = kwargs["json"]
        self.assertEqual(body["id"], "abc123")
        self.assertEqual(body["attendees"], [{"email": "a@example.com"}])
        self.assertEqual(body["start"], {"dateTime": "2026-11-20T10:00:00+00:00", "timeZone": "UTC"})
        self.assertEqual(
            body["conferenceData"]["createRequest"]["conferenceSolutionKey"], {"type": "hangoutsMeet"}
        )
        self.assertNotIn("location", body)

    @mock.patch(REQUEST)
    def test_link_taken_from_entry_points(self, request):
        request.return_value = response(
            body={
                "id": "abc123",
                "conferenceData": {
                    "entryPoints": [
                        {"entryPointType": "phone", "uri": "tel:+1"},
                        {"entryPointType": "video", "uri": "https://meet.google.com/y"},
                    ]
                },
            }
        )

        self.assertEqual(
            self.provider.create_event(self.owner, make_event()).meet_link, "https://meet.google.com/y"
        )

    @mock.patch(REQUEST)
    def test_pending_link_is_polled(self, request):
        request.side_effect = [
            response(body={"id": "abc123"}),
            response(body={"id": "abc123"}),
            response(body={"id": "abc123", "hangoutLink": "https://meet.google.com/z"}),
        ]

        result = self.provider.create_event(self.owner, make_event())

        self.assertEqual(result.meet_link, "https://meet.google.com/z")
        self.assertEqual(request.call_count, 3)

    @mock.patch(REQUEST)
    def test_missing_link_after_polling_fails(self, request):
        request.return_value = response(body={"id": "abc123"})

        with self.assertRaises(VideoConferenceError):
            self.provider.create_event(self.owner, make_event())

    @mock.patch(REQUEST)
    def test_duplicate_create_reuses_existing_event(self, request):
        request.side_effect = [
            response(409, {"error": {"message": "identifier already exists"}}),
            response(body={"id": "abc123", "status": "confirmed", "hangoutLink": "https://meet.google.com/w"}),
        ]

        result = self.provider.create_event(self.owner, make_event())

        self.assertEqual(result.meet_link, "https://meet.google.com/w")
        self.assertEqual(request.call_args.args[0], "GET")

    @mock.patch(REQUEST)
    def test_google_error_is_wrapped_with_message(self, request):
        request.return_value = response(403, {"error": {"message": "Forbidden thing"}})

        with self.assertRaises(VideoConferenceError) as ctx:
            self.provider.create_event(self.owner, make_event())

        self.assertIn("403", str(ctx.exception))
        self.assertIn("Forbidden thing", str(ctx.exception))

    @mock.patch(REQUEST)
    def test_network_error_is_wrapped(self, request):
        request.side_effect = google_meet_provider.requests.ConnectionError("down")

        with self.assertRaises(VideoConferenceError):
            self.provider.create_event(self.owner, make_event())

    def test_not_connected_owner(self):
        provider = GoogleMeetProvider(FakeTokenService(connected=False))

        self.assertIsNone(provider.get_connected_account_email(self.owner))
        with self.assertRaises(VideoConferenceNotConnectedError):
            provider.create_event(self.owner, make_event())

    @mock.patch(REQUEST)
    def test_update_patches_with_send_updates(self, request):
        request.return_value = response(body={})

        self.provider.update_event(self.owner, "evt", make_event(description=None))

        args, kwargs = request.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertTrue(args[1].endswith("/events/evt"))
        self.assertEqual(kwargs["params"]["sendUpdates"], "all")
        self.assertEqual(kwargs["json"]["description"], "")
        self.assertNotIn("conferenceData", kwargs["json"])

    @mock.patch(REQUEST)
    def test_cancel_sends_cancellations(self, request):
        request.return_value = response(204)

        self.provider.cancel_event(self.owner, "evt")

        args, kwargs = request.call_args
        self.assertEqual(args[0], "DELETE")
        self.assertEqual(kwargs["params"], {"sendUpdates": "all"})

    @mock.patch(REQUEST)
    def test_cancel_of_missing_event_is_ok(self, request):
        for code in (404, 410):
            request.return_value = response(code)
            self.provider.cancel_event(self.owner, "evt")

    @mock.patch(REQUEST)
    def test_cancel_error_raises(self, request):
        request.return_value = response(500)

        with self.assertRaises(VideoConferenceError):
            self.provider.cancel_event(self.owner, "evt")


if __name__ == "__main__":
    unittest.main()
