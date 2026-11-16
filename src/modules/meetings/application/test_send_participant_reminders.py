from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    MeetingReminderNotifier,
)
from src.modules.meetings.application.use_cases.send_meeting_participant_reminders import (
    SendMeetingParticipantRemindersUseCase,
)
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class Repo:
    def __init__(self, meetings):
        self.meetings = meetings

    def get_conference_meetings_not_ended(self, as_of):
        return [m for m in self.meetings if m.end_at > as_of]

    def get_by_id_with_details(self, meeting_id):
        return SimpleNamespace(host_name="Don Davis")

    def save(self, meeting):
        return meeting


class Conference:
    def __init__(self, emails):
        self.emails = emails

    def reminder_recipient_emails(self, meeting):
        return self.emails


class Notifier(MeetingReminderNotifier):
    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def send(self, recipient_email, reminder):
        if recipient_email in self.fail_for:
            raise RuntimeError("relay down")
        self.sent.append((recipient_email, reminder))


def make_meeting(start_in_minutes, created_minutes_ago=120, reminder_at=None):
    start = NOW + timedelta(minutes=start_in_minutes)
    meeting = Meeting.create(
        title="Demo",
        start_at=start,
        end_at=start + timedelta(hours=1),
        host_id=uuid4(),
        created_by_id=uuid4(),
        reminder_at=reminder_at,
    )
    meeting.created_at = NOW - timedelta(minutes=created_minutes_ago)
    meeting.conference_status = ConferenceStatus.CREATED
    meeting.meet_link = "https://meet.google.com/abc-defg-hij"
    return meeting


def run(meeting, emails=("a@x.com", "b@x.com"), notifier=None):
    notifier = notifier or Notifier()
    sent = SendMeetingParticipantRemindersUseCase(
        Repo([meeting]), Conference(emails), notifier
    ).execute(NOW)
    return sent, notifier


class SendParticipantRemindersTests(TestCase):
    def test_sends_to_every_participant_with_the_meet_link(self):
        sent, notifier = run(make_meeting(10))
        self.assertEqual(sent, 2)
        self.assertEqual({e for e, _ in notifier.sent}, {"a@x.com", "b@x.com"})
        self.assertEqual(notifier.sent[0][1].meet_link, "https://meet.google.com/abc-defg-hij")

    def test_not_due_yet(self):
        sent, _ = run(make_meeting(60))
        self.assertEqual(sent, 0)

    def test_sent_only_once_per_reminder_time(self):
        meeting = make_meeting(10)
        run(meeting)
        sent, _ = run(meeting)
        self.assertEqual(sent, 0)

    def test_rescheduled_meeting_is_reminded_again(self):
        meeting = make_meeting(10)
        run(meeting)
        meeting.start_at += timedelta(minutes=5)
        meeting.end_at += timedelta(minutes=5)
        sent, _ = run(meeting)
        self.assertEqual(sent, 2)

    def test_custom_reminder_at_is_honoured(self):
        meeting = make_meeting(24 * 60, reminder_at=NOW - timedelta(minutes=1))
        sent, _ = run(meeting)
        self.assertEqual(sent, 2)

    def test_meeting_created_inside_the_window_is_not_reminded(self):
        sent, notifier = run(make_meeting(5, created_minutes_ago=1))
        self.assertEqual(sent, 0)
        self.assertEqual(notifier.sent, [])

    def test_total_failure_is_retried_next_run(self):
        meeting = make_meeting(10)
        sent, _ = run(meeting, notifier=Notifier(fail_for=("a@x.com", "b@x.com")))
        self.assertEqual(sent, 0)
        self.assertIsNone(meeting.participant_reminder_for)
        sent, _ = run(meeting)
        self.assertEqual(sent, 2)

    def test_partial_failure_still_marks_sent(self):
        meeting = make_meeting(10)
        sent, _ = run(meeting, notifier=Notifier(fail_for=("a@x.com",)))
        self.assertEqual(sent, 1)
        self.assertIsNotNone(meeting.participant_reminder_for)

    def test_finished_meeting_is_ignored(self):
        meeting = make_meeting(-120)
        sent, _ = run(meeting)
        self.assertEqual(sent, 0)
