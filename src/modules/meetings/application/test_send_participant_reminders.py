from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    KIND_REMINDER,
    MeetingReminder,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.services.meeting_recipients import MeetingRecipients
from src.modules.meetings.application.use_cases.send_meeting_participant_reminders import (
    SendMeetingParticipantRemindersUseCase,
)
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class Repo:
    def __init__(self, meetings):
        self.meetings = meetings

    def get_email_reminder_candidates(self, as_of):
        return [
            m for m in self.meetings if m.send_email_notifications and m.end_at > as_of
        ]

    def save(self, meeting):
        return meeting


class Notifications:
    """Stands in for MeetingNotificationService."""

    def __init__(self, emails, skipped=()):
        self.emails = tuple(emails)
        self.skipped = tuple(skipped)

    def reminder_recipients(self, meeting):
        return MeetingRecipients(self.emails, self.skipped)

    def build_email(self, meeting, kind):
        return MeetingReminder(
            title=meeting.title,
            start_at=meeting.start_at,
            end_at=meeting.end_at,
            host_name="Don Davis",
            meet_link=meeting.meet_link,
            location=meeting.location,
            description=meeting.description,
            kind=kind,
        )


class Notifier(MeetingReminderNotifier):
    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def send(self, recipient_email, reminder):
        if recipient_email in self.fail_for:
            raise RuntimeError("relay down")
        self.sent.append((recipient_email, reminder))


def make_meeting(
    start_in_minutes,
    created_minutes_ago=120,
    reminder_at=None,
    with_meet=True,
    notify=True,
):
    start = NOW + timedelta(minutes=start_in_minutes)
    meeting = Meeting.create(
        title="Demo",
        description="Agenda: pricing review",
        start_at=start,
        end_at=start + timedelta(hours=1),
        host_id=uuid4(),
        created_by_id=uuid4(),
        reminder_at=reminder_at,
        send_email_notifications=notify,
    )
    meeting.created_at = NOW - timedelta(minutes=created_minutes_ago)
    if with_meet:
        meeting.conference_status = ConferenceStatus.CREATED
        meeting.meet_link = "https://meet.google.com/abc-defg-hij"
    return meeting


def run(meeting, emails=("a@x.com", "b@x.com"), notifier=None):
    notifier = notifier or Notifier()
    sent = SendMeetingParticipantRemindersUseCase(
        Repo([meeting]), Notifications(emails), notifier
    ).execute(NOW)
    return sent, notifier


class SendParticipantRemindersTests(TestCase):
    def test_sends_to_every_recipient_with_the_meet_link(self):
        sent, notifier = run(make_meeting(10))
        self.assertEqual(sent, 2)
        self.assertEqual({e for e, _ in notifier.sent}, {"a@x.com", "b@x.com"})
        self.assertEqual(notifier.sent[0][1].meet_link, "https://meet.google.com/abc-defg-hij")

    def test_meeting_without_meet_is_still_reminded(self):
        sent, notifier = run(make_meeting(10, with_meet=False))
        self.assertEqual(sent, 2)
        self.assertIsNone(notifier.sent[0][1].meet_link)

    def test_reminder_carries_heading_and_description(self):
        _, notifier = run(make_meeting(10, with_meet=False))
        reminder = notifier.sent[0][1]
        self.assertEqual(reminder.title, "Demo")
        self.assertEqual(reminder.description, "Agenda: pricing review")
        self.assertEqual(reminder.kind, KIND_REMINDER)

    def test_meeting_with_email_notifications_off_is_not_reminded(self):
        sent, notifier = run(make_meeting(10, notify=False))
        self.assertEqual(sent, 0)
        self.assertEqual(notifier.sent, [])

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

    def test_unreachable_recipients_do_not_block_the_reminder(self):
        meeting = make_meeting(10)
        skipped = (SimpleNamespace(name="No Email"),)
        sent = SendMeetingParticipantRemindersUseCase(
            Repo([meeting]), Notifications(("a@x.com",), skipped), Notifier()
        ).execute(NOW)
        self.assertEqual(sent, 1)
