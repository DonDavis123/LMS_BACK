import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.meetings.application.dto.create_meeting import CreateMeetingDTO
from src.modules.meetings.application.dto.get_meeting import GetMeetingDTO, MeetingParticipantDTO
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO
from src.modules.meetings.application.interfaces.video_conference_provider import (
    ConferenceEventResult,
    VideoConferenceError,
    VideoConferenceNotConnectedError,
    VideoConferenceProvider,
)
from src.modules.meetings.application.services.meeting_conference_service import (
    MeetingConferenceService,
)
from src.modules.meetings.application.tests import (
    FakeContactRepo,
    FakeLeadRepo,
    FakeMeetingRepo,
    FakeTimelineRecorder,
    FakeTransaction,
    FakeUserRepo,
    user,
)
from src.modules.meetings.application.use_cases.add_meeting_conference import (
    AddMeetingConferenceUseCase,
)
from src.modules.meetings.application.use_cases.create_meeting import CreateMeetingUseCase
from src.modules.meetings.application.use_cases.delete_meeting import DeleteMeetingUseCase
from src.modules.meetings.application.use_cases.update_meeting import UpdateMeetingUseCase
from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType


class FakeProvider(VideoConferenceProvider):
    def __init__(self, connected_users=None):
        # user id -> google account email
        self.connected = dict(connected_users or {})
        self.created = []
        self.updated = []
        self.cancelled = []
        self.fail_create = False
        self.fail_update = False

    @property
    def provider_type(self):
        return ConferenceProvider.GOOGLE_MEET

    def get_connected_account_email(self, user_id):
        return self.connected.get(user_id)

    def create_event(self, owner_user_id, event):
        if self.fail_create:
            raise VideoConferenceError("Google Calendar error (500)")
        self.created.append((owner_user_id, event))
        return ConferenceEventResult(event_id="evt-1", meet_link="https://meet.google.com/abc-defg-hij")

    def update_event(self, owner_user_id, event_id, event):
        if self.fail_update:
            raise VideoConferenceError("Google Calendar error (500)")
        self.updated.append((owner_user_id, event_id, event))

    def cancel_event(self, owner_user_id, event_id):
        self.cancelled.append((owner_user_id, event_id))


class GoogleMeetUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.host = user()
        self.host.email = "host@example.com"
        self.users = {self.host.id: self.host}
        self.repo = FakeMeetingRepo()
        self.provider = FakeProvider({self.host.id: "host@gmail.com"})
        user_repo = FakeUserRepo(self.users)
        self.service = MeetingConferenceService(self.repo, user_repo, self.provider)
        self.create = CreateMeetingUseCase(
            self.repo,
            user_repo,
            FakeLeadRepo({}),
            FakeContactRepo({}),
            FakeTimelineRecorder(),
            FakeTransaction(),
            None,
            self.service,
        )

    def dto(self, **kw):
        now = datetime.now(timezone.utc) + timedelta(days=1)
        data = dict(
            title="Demo",
            start_at=now,
            end_at=now + timedelta(hours=1),
            host_id=self.host.id,
            created_by_id=self.host.id,
            add_google_meet=True,
        )
        data.update(kw)
        return CreateMeetingDTO(**data)

    def set_participants(self, meeting, participants):
        self.repo.details[meeting.id] = GetMeetingDTO(
            meeting=meeting,
            host_id=meeting.host_id,
            host_name="Host",
            created_by_id=meeting.created_by_id,
            created_by_name="Host",
            related_to=(),
            participants=tuple(participants),
        )

    # ---- create ----

    def test_create_without_meet_never_touches_google(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))

        self.assertEqual(meeting.conference_status, ConferenceStatus.NONE)
        self.assertIsNone(meeting.meet_link)
        self.assertEqual(self.provider.created, [])

    def test_create_with_meet_stores_link_and_event(self):
        meeting = self.create.execute(self.dto())

        self.assertEqual(meeting.conference_status, ConferenceStatus.CREATED)
        self.assertEqual(meeting.meet_link, "https://meet.google.com/abc-defg-hij")
        self.assertEqual(meeting.external_event_id, "evt-1")
        self.assertEqual(meeting.calendar_owner_id, self.host.id)
        self.assertEqual(meeting.conference_provider, ConferenceProvider.GOOGLE_MEET)
        self.assertEqual(self.provider.created[0][0], self.host.id)
        self.assertEqual(self.provider.created[0][1].client_event_id, meeting.id.hex)

    def test_create_fails_fast_when_host_not_connected(self):
        self.provider.connected.clear()

        with self.assertRaises(VideoConferenceNotConnectedError) as ctx:
            self.create.execute(self.dto())

        self.assertIn("Connect your Google account", str(ctx.exception))
        self.assertEqual(self.repo.meetings, {})

    def test_create_message_differs_when_someone_else_is_host(self):
        other = user()
        self.users[other.id] = other

        with self.assertRaises(VideoConferenceNotConnectedError) as ctx:
            self.create.execute(self.dto(host_id=other.id))

        self.assertIn("host must connect", str(ctx.exception))
        self.assertEqual(self.repo.meetings, {})

    def test_create_rejects_all_day_with_meet(self):
        with self.assertRaises(ValueError):
            self.create.execute(self.dto(is_all_day=True))

        self.assertEqual(self.repo.meetings, {})

    def test_google_failure_keeps_meeting_and_marks_failed(self):
        self.provider.fail_create = True

        meeting = self.create.execute(self.dto())

        self.assertIn(meeting.id, self.repo.meetings)
        self.assertEqual(meeting.conference_status, ConferenceStatus.FAILED)
        self.assertIn("Google Calendar error", meeting.conference_error)
        self.assertIsNone(meeting.meet_link)

    # ---- attendees ----

    def test_attendees_are_participants_deduped_without_host(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))
        self.set_participants(
            meeting,
            [
                MeetingParticipantDTO(self.host.id, MeetingParticipantType.USER, "Host", "host@gmail.com"),
                MeetingParticipantDTO(uuid4(), MeetingParticipantType.LEAD, "Lead", "lead@example.com"),
                MeetingParticipantDTO(uuid4(), MeetingParticipantType.CONTACT, "Contact", "LEAD@example.com"),
                MeetingParticipantDTO(uuid4(), MeetingParticipantType.CONTACT, "No email", None),
                MeetingParticipantDTO(uuid4(), MeetingParticipantType.CONTACT, "Bad email", "not-an-email"),
                MeetingParticipantDTO(uuid4(), MeetingParticipantType.LEAD, "Host again", "Host@Example.com"),
            ],
        )

        self.service.attach(meeting)

        self.assertEqual(self.provider.created[0][1].attendee_emails, ("lead@example.com",))

    # ---- update ----

    def make_meeting_with_meet(self):
        meeting = self.create.execute(self.dto())
        self.update = UpdateMeetingUseCase(
            self.repo,
            FakeUserRepo(self.users),
            FakeLeadRepo({}),
            FakeContactRepo({}),
            FakeTimelineRecorder(),
            FakeTransaction(),
            None,
            self.service,
        )
        self.set_participants(meeting, [])
        return meeting

    def test_update_of_title_patches_google_event(self):
        meeting = self.make_meeting_with_meet()

        self.update.execute(UpdateMeetingDTO(meeting.id, {"title": "New title"}), self.host.id)

        self.assertEqual(len(self.provider.updated), 1)
        owner, event_id, event = self.provider.updated[0]
        self.assertEqual((owner, event_id, event.title), (self.host.id, "evt-1", "New title"))

    def test_update_of_unrelated_field_does_not_touch_google(self):
        meeting = self.make_meeting_with_meet()

        self.update.execute(
            UpdateMeetingDTO(meeting.id, {"reminder_at": datetime.now(timezone.utc)}),
            self.host.id,
        )

        self.assertEqual(self.provider.updated, [])

    def test_update_never_calls_google_for_meeting_without_meet(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))
        update = UpdateMeetingUseCase(
            self.repo, FakeUserRepo(self.users), FakeLeadRepo({}), FakeContactRepo({}),
            FakeTimelineRecorder(), FakeTransaction(), None, self.service,
        )
        self.set_participants(meeting, [])

        update.execute(UpdateMeetingDTO(meeting.id, {"title": "Changed"}), self.host.id)

        self.assertEqual(self.provider.updated, [])

    def test_update_sync_failure_keeps_link_and_records_error(self):
        meeting = self.make_meeting_with_meet()
        self.provider.fail_update = True

        saved = self.update.execute(UpdateMeetingDTO(meeting.id, {"title": "New"}), self.host.id)

        self.assertEqual(saved.title, "New")
        self.assertEqual(saved.conference_status, ConferenceStatus.CREATED)
        self.assertIsNotNone(saved.meet_link)
        self.assertIn("Google Calendar error", saved.conference_error)

    def test_update_cannot_make_meet_meeting_all_day(self):
        meeting = self.make_meeting_with_meet()

        with self.assertRaises(ValueError):
            self.update.execute(UpdateMeetingDTO(meeting.id, {"is_all_day": True}), self.host.id)

    # ---- delete ----

    def test_delete_cancels_google_event(self):
        meeting = self.make_meeting_with_meet()
        delete = DeleteMeetingUseCase(
            self.repo, FakeTimelineRecorder(), FakeTransaction(), None, self.service,
        )

        delete.execute(meeting.id, self.host.id)

        self.assertEqual(self.provider.cancelled, [(self.host.id, "evt-1")])

    def test_delete_without_meet_does_not_call_google(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))
        self.set_participants(meeting, [])
        delete = DeleteMeetingUseCase(
            self.repo, FakeTimelineRecorder(), FakeTransaction(), None, self.service,
        )

        delete.execute(meeting.id, self.host.id)

        self.assertEqual(self.provider.cancelled, [])

    # ---- add / retry ----

    def test_add_conference_to_existing_meeting(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))
        self.set_participants(meeting, [])
        add = AddMeetingConferenceUseCase(self.repo, self.service)

        result = add.execute(meeting.id, self.host.id)

        self.assertEqual(result.conference_status, ConferenceStatus.CREATED)
        self.assertEqual(result.meet_link, "https://meet.google.com/abc-defg-hij")

    def test_retry_after_failure_succeeds(self):
        self.provider.fail_create = True
        meeting = self.create.execute(self.dto())
        self.assertEqual(meeting.conference_status, ConferenceStatus.FAILED)

        self.provider.fail_create = False
        result = AddMeetingConferenceUseCase(self.repo, self.service).execute(meeting.id, self.host.id)

        self.assertEqual(result.conference_status, ConferenceStatus.CREATED)
        self.assertIsNone(result.conference_error)

    def test_add_conference_requires_connected_host(self):
        meeting = self.create.execute(self.dto(add_google_meet=False))
        self.provider.connected.clear()

        with self.assertRaises(VideoConferenceNotConnectedError):
            AddMeetingConferenceUseCase(self.repo, self.service).execute(meeting.id, self.host.id)

    def test_add_conference_on_existing_event_resyncs(self):
        meeting = self.make_meeting_with_meet()

        AddMeetingConferenceUseCase(self.repo, self.service).execute(meeting.id, self.host.id)

        self.assertEqual(len(self.provider.created), 1)
        self.assertEqual(len(self.provider.updated), 1)

    def test_add_conference_missing_meeting(self):
        with self.assertRaises(ValueError):
            AddMeetingConferenceUseCase(self.repo, self.service).execute(uuid4(), self.host.id)


if __name__ == "__main__":
    unittest.main()
