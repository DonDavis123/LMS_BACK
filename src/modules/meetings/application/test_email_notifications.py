"""Email notifications for meetings: with/without Google Meet, Related To
recipients, skipped recipients, updates, cancellation and the reminder."""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.meetings.application.dto.create_meeting import CreateMeetingDTO
from src.modules.meetings.application.dto.get_meeting import (
    GetMeetingDTO,
    MeetingParticipantDTO,
    MeetingRelatedRecordDTO,
)
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO
from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    KIND_CANCELLATION,
    KIND_INVITATION,
    KIND_REMINDER,
    KIND_UPDATE,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.services.meeting_conference_service import (
    MeetingConferenceService,
)
from src.modules.meetings.application.services.meeting_notification_service import (
    MeetingNotificationService,
)
from src.modules.meetings.application.test_google_meet import FakeProvider
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
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import (
    MeetingRelatedRecordType,
)


class FakeNotifier(MeetingReminderNotifier):
    def __init__(self):
        self.sent = []

    def send(self, recipient_email, reminder):
        self.sent.append((recipient_email, reminder))

    def to(self, kind):
        return sorted(e for e, r in self.sent if r.kind == kind)


class EmailNotificationTests(unittest.TestCase):
    def setUp(self):
        self.host = user()
        self.host.email = "host@example.com"
        self.host.name = "Host"
        self.colleague = user()
        self.colleague.email = "colleague@example.com"
        self.colleague.name = "Colleague"
        self.users = {self.host.id: self.host, self.colleague.id: self.colleague}
        self.user_repo = FakeUserRepo(self.users)
        self.repo = FakeMeetingRepo()
        self.provider = FakeProvider({self.host.id: "host@gmail.com"})
        self.notifier = FakeNotifier()
        self.conference = MeetingConferenceService(self.repo, self.user_repo, self.provider)
        self.notifications = MeetingNotificationService(
            self.repo, self.user_repo, self.notifier, self.conference
        )
        self.create = CreateMeetingUseCase(
            self.repo, self.user_repo, FakeLeadRepo({}), FakeContactRepo({}),
            FakeTimelineRecorder(), FakeTransaction(), None,
            self.conference, self.notifications,
        )

    # -- helpers ---------------------------------------------------------

    def dto(self, **kw):
        start = datetime.now(timezone.utc) + timedelta(days=1)
        data = dict(
            title="Pricing review",
            description="Agenda: Q4 pricing",
            start_at=start,
            end_at=start + timedelta(hours=1),
            host_id=self.host.id,
            created_by_id=self.host.id,
            send_email_notifications=True,
        )
        data.update(kw)
        return CreateMeetingDTO(**data)

    def lead_participant(self, email="lead@example.com", name="Lead"):
        return MeetingParticipantDTO(uuid4(), MeetingParticipantType.LEAD, name, email)

    def set_details(self, meeting, participants=(), related=()):
        self.repo.details[meeting.id] = GetMeetingDTO(
            meeting=meeting, host_id=meeting.host_id, host_name="Host",
            created_by_id=meeting.created_by_id, created_by_name="Host",
            related_to=tuple(related), participants=tuple(participants),
        )

    def make(self, participants=(), related=(), connected=False, **kw):
        """Create through the use case with the guest list in place."""
        if not connected:
            self.provider.connected.clear()
        original = self.repo.save_with_relationships

        def save_with_relationships(meeting, related_groups=(), participant_groups=()):
            saved = original(meeting, related_groups, participant_groups)
            self.set_details(saved, participants, related)
            return saved

        self.repo.save_with_relationships = save_with_relationships
        return self.create.execute(self.dto(**kw))

    # -- create ----------------------------------------------------------

    def test_no_meet_no_google_still_emails_invitations_with_title_and_description(self):
        meeting = self.make(participants=[self.lead_participant()])

        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])
        _, email = self.notifier.sent[0]
        self.assertEqual(email.title, "Pricing review")
        self.assertEqual(email.description, "Agenda: Q4 pricing")
        self.assertIsNone(email.meet_link)
        self.assertEqual(self.provider.created, [])
        self.assertEqual(meeting.conference_status, ConferenceStatus.NONE)

    def test_related_to_records_are_emailed_too(self):
        related = [
            MeetingRelatedRecordDTO(uuid4(), MeetingRelatedRecordType.LEAD, "Acme lead", "acme@example.com"),
            MeetingRelatedRecordDTO(uuid4(), MeetingRelatedRecordType.CONTACT, "Jo", "jo@example.com"),
        ]
        self.make(related=related)

        self.assertEqual(
            self.notifier.to(KIND_INVITATION), ["acme@example.com", "jo@example.com"]
        )

    def test_assigned_host_is_invited_when_someone_else_schedules(self):
        self.make(created_by_id=self.colleague.id)

        self.assertEqual(self.notifier.to(KIND_INVITATION), ["host@example.com"])

    def test_email_off_sends_nothing(self):
        self.make(
            participants=[self.lead_participant()], send_email_notifications=False
        )

        self.assertEqual(self.notifier.sent, [])
        self.assertEqual(self.provider.created, [])

    def test_option_follows_meet_when_not_given(self):
        meeting = self.make(
            connected=True, add_google_meet=True, send_email_notifications=None
        )
        self.assertTrue(meeting.send_email_notifications)

        meeting = self.make(
            connected=True, add_google_meet=False, send_email_notifications=None
        )
        self.assertFalse(meeting.send_email_notifications)

    def test_connected_host_gets_a_calendar_event_instead_of_our_invite(self):
        meeting = self.make(participants=[self.lead_participant()], connected=True)

        self.assertEqual(len(self.provider.created), 1)
        _, event = self.provider.created[0]
        self.assertFalse(event.with_meet)
        self.assertTrue(event.notify_attendees)
        self.assertEqual(event.attendee_emails, ("lead@example.com",))
        self.assertEqual(meeting.external_event_id, "evt-1")
        self.assertIsNone(meeting.meet_link)
        self.assertEqual(meeting.conference_status, ConferenceStatus.NONE)
        self.assertEqual(self.notifier.sent, [])  # Google sends the invite

    def test_calendar_event_failure_falls_back_to_our_email(self):
        self.provider.fail_create = True
        meeting = self.make(participants=[self.lead_participant()], connected=True)

        self.assertIsNone(meeting.external_event_id)
        self.assertEqual(meeting.conference_status, ConferenceStatus.NONE)
        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])

    def test_all_day_meeting_uses_our_email_not_a_calendar_event(self):
        self.make(
            participants=[self.lead_participant()], connected=True, is_all_day=True
        )

        self.assertEqual(self.provider.created, [])
        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])

    def test_google_event_includes_related_to_and_organizer_reminders(self):
        related = [
            MeetingRelatedRecordDTO(uuid4(), MeetingRelatedRecordType.LEAD, "Acme", "acme@example.com")
        ]
        meeting = self.make(related=related, connected=True, add_google_meet=True)

        _, event = self.provider.created[0]
        self.assertTrue(event.with_meet)
        self.assertEqual(event.attendee_emails, ("acme@example.com",))
        self.assertEqual(event.reminder_minutes, 15)
        self.assertEqual(meeting.conference_status, ConferenceStatus.CREATED)

    def test_custom_reminder_time_sets_google_reminder_minutes(self):
        start = datetime.now(timezone.utc) + timedelta(days=1)
        self.make(
            connected=True, add_google_meet=True, start_at=start,
            end_at=start + timedelta(hours=1), reminder_at=start - timedelta(minutes=45),
        )

        self.assertEqual(self.provider.created[0][1].reminder_minutes, 45)

    def test_people_without_a_usable_email_are_reported_not_silently_skipped(self):
        participants = [
            self.lead_participant("lead@example.com", "Has Email"),
            self.lead_participant(None, "No Email"),
            self.lead_participant("not-an-email", "Bad Email"),
        ]
        meeting = self.make(participants=participants)

        skipped = {item["name"]: item["reason"] for item in meeting.email_skipped}
        self.assertEqual(skipped, {"No Email": "no_email", "Bad Email": "invalid_email"})
        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])

    def test_skipped_people_are_reported_with_google_too(self):
        meeting = self.make(
            participants=[self.lead_participant(None, "No Email")],
            connected=True, add_google_meet=True,
        )

        self.assertEqual([i["name"] for i in meeting.email_skipped], ["No Email"])

    def test_same_lead_as_participant_and_related_is_emailed_once(self):
        lead = self.lead_participant()
        related = [
            MeetingRelatedRecordDTO(lead.id, MeetingRelatedRecordType.LEAD, "Lead", "lead@example.com")
        ]
        self.make(participants=[lead], related=related)

        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])

    # -- update ----------------------------------------------------------

    def updater(self):
        return UpdateMeetingUseCase(
            self.repo, self.user_repo, FakeLeadRepo({}), FakeContactRepo({}),
            FakeTimelineRecorder(), FakeTransaction(), None,
            self.conference, self.notifications,
        )

    def test_update_without_event_emails_existing_guests(self):
        lead = self.lead_participant()
        meeting = self.make(participants=[lead])
        self.notifier.sent.clear()

        self.updater().execute(
            UpdateMeetingDTO(meeting.id, {"title": "Renamed"}), self.host.id
        )

        self.assertEqual(self.notifier.to(KIND_UPDATE), ["lead@example.com"])
        self.assertEqual(self.notifier.sent[0][1].title, "Renamed")

    def test_update_that_changes_nothing_visible_sends_nothing(self):
        meeting = self.make(participants=[self.lead_participant()])
        self.notifier.sent.clear()

        self.updater().execute(
            UpdateMeetingDTO(meeting.id, {"reminder_at": datetime.now(timezone.utc)}),
            self.host.id,
        )

        self.assertEqual(self.notifier.sent, [])

    def test_turning_email_on_invites_everyone(self):
        meeting = self.make(
            participants=[self.lead_participant()], send_email_notifications=False
        )
        self.assertEqual(self.notifier.sent, [])

        self.updater().execute(
            UpdateMeetingDTO(meeting.id, {"send_email_notifications": True}), self.host.id
        )

        self.assertEqual(self.notifier.to(KIND_INVITATION), ["lead@example.com"])

    def test_update_with_email_off_sends_nothing(self):
        meeting = self.make(
            participants=[self.lead_participant()], send_email_notifications=False
        )

        self.updater().execute(UpdateMeetingDTO(meeting.id, {"title": "x"}), self.host.id)

        self.assertEqual(self.notifier.sent, [])

    def test_update_with_google_event_is_synced_not_emailed_by_us(self):
        meeting = self.make(
            participants=[self.lead_participant()], connected=True
        )

        self.updater().execute(UpdateMeetingDTO(meeting.id, {"title": "Renamed"}), self.host.id)

        self.assertEqual(len(self.provider.updated), 1)
        self.assertEqual(self.notifier.sent, [])

    # -- delete ----------------------------------------------------------

    def test_delete_without_event_emails_cancellation(self):
        meeting = self.make(participants=[self.lead_participant()])
        self.notifier.sent.clear()

        DeleteMeetingUseCase(
            self.repo, FakeTimelineRecorder(), FakeTransaction(), None,
            self.conference, self.notifications,
        ).execute(meeting.id, self.host.id)

        self.assertEqual(self.notifier.to(KIND_CANCELLATION), ["lead@example.com"])

    # -- reminder recipients --------------------------------------------

    def test_reminder_goes_to_host_and_guests_when_there_is_no_google_event(self):
        meeting = self.make(
            participants=[
                self.lead_participant(),
                MeetingParticipantDTO(
                    self.colleague.id, MeetingParticipantType.USER, "Colleague",
                    "colleague@example.com",
                ),
            ]
        )

        recipients = self.notifications.reminder_recipients(meeting)

        self.assertEqual(
            sorted(recipients.emails),
            ["colleague@example.com", "host@example.com", "lead@example.com"],
        )

    def test_reminder_skips_the_calendar_owner_who_gets_google_reminders(self):
        meeting = self.make(participants=[self.lead_participant()], connected=True)

        recipients = self.notifications.reminder_recipients(meeting)

        self.assertEqual(recipients.emails, ("lead@example.com",))

    def test_reminder_email_content(self):
        meeting = self.make()
        email = self.notifications.build_email(meeting, KIND_REMINDER)
        self.assertEqual((email.title, email.description), ("Pricing review", "Agenda: Q4 pricing"))
        self.assertEqual(email.host_name, "Host")

    # -- add Meet later --------------------------------------------------

    def test_adding_meet_to_a_calendar_only_event_reuses_the_event(self):
        meeting = self.make(participants=[self.lead_participant()], connected=True)
        self.assertIsNone(meeting.meet_link)

        result = AddMeetingConferenceUseCase(self.repo, self.conference).execute(
            meeting.id, self.host.id
        )

        self.assertEqual(len(self.provider.created), 1)  # no second event
        self.assertEqual(result.conference_status, ConferenceStatus.CREATED)
        self.assertEqual(result.meet_link, "https://meet.google.com/abc-defg-hij")
        self.assertTrue(self.provider.updated[0][2].with_meet)

    def test_adding_meet_turns_email_on_so_people_are_invited(self):
        self.provider.connected[self.host.id] = "host@gmail.com"
        meeting = self.make(send_email_notifications=False, connected=True)

        result = AddMeetingConferenceUseCase(self.repo, self.conference).execute(
            meeting.id, self.host.id
        )

        self.assertTrue(result.send_email_notifications)
        self.assertTrue(self.provider.created[0][1].notify_attendees)


if __name__ == "__main__":
    unittest.main()
