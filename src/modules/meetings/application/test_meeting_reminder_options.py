from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    KIND_REMINDER,
    MeetingReminder,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.services.meeting_notification_service import (
    MeetingNotificationService,
)
from src.modules.meetings.application.services.meeting_recipients import MeetingRecipients
from src.modules.meetings.application.use_cases.send_meeting_participant_reminders import (
    SendMeetingParticipantRemindersUseCase,
)
from src.modules.meetings.domain.entities.meeting import Meeting, normalize_reminder_offsets
from src.modules.meetings.infrastructure.meeting_reminder_emailer import MeetingReminderEmailer

START = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


class Repo:
    def __init__(self, meeting):
        self.meeting = meeting

    def get_email_reminder_candidates(self, as_of):
        return [self.meeting]

    def save(self, meeting):
        return meeting


class Notifications:
    def reminder_recipients(self, meeting):
        return MeetingRecipients(("a@x.com", "b@x.com"), ())

    def build_email(self, meeting, kind):
        return MeetingReminder(
            title=meeting.title, start_at=meeting.start_at, end_at=meeting.end_at,
            host_name="Host", description=meeting.description, kind=kind,
        )


class Notifier(MeetingReminderNotifier):
    def __init__(self):
        self.sent = []

    def send(self, recipient_email, reminder):
        self.sent.append(recipient_email)


def make(offsets, created_days_ago=3, **kwargs):
    meeting = Meeting.create(
        title="Demo", description="Agenda", start_at=START, end_at=START + timedelta(hours=1),
        host_id=uuid4(), created_by_id=uuid4(), reminder_offsets=offsets, **kwargs,
    )
    meeting.created_at = START - timedelta(days=created_days_ago)
    return meeting


def run(meeting, minutes_before_start):
    notifier = Notifier()
    sent = SendMeetingParticipantRemindersUseCase(
        Repo(meeting), Notifications(), notifier
    ).execute(START - timedelta(minutes=minutes_before_start))
    return sent, notifier


class NormalizeTests(TestCase):
    def test_none_empty_and_sorted(self):
        self.assertIsNone(normalize_reminder_offsets(None))
        self.assertEqual(normalize_reminder_offsets([]), [])
        self.assertEqual(normalize_reminder_offsets([15, 1440, 15, 60]), [1440, 60, 15])

    def test_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            normalize_reminder_offsets([45])
        with self.assertRaises(ValueError):
            normalize_reminder_offsets(["abc"])


class SelectedRemindersTests(TestCase):
    def test_each_chosen_reminder_is_sent_once(self):
        meeting = make([1440, 60, 15], send_email_notifications=True)
        self.assertEqual(run(meeting, 1500)[0], 0)  # nothing due yet
        self.assertEqual(run(meeting, 1440)[0], 2)  # 1 day before
        self.assertEqual(run(meeting, 1439)[0], 0)  # not sent twice
        self.assertEqual(run(meeting, 60)[0], 2)    # 1 hour before
        self.assertEqual(run(meeting, 15)[0], 2)    # 15 minutes before
        self.assertEqual(run(meeting, 5)[0], 0)

    def test_none_sends_nothing(self):
        meeting = make([], send_email_notifications=True)
        self.assertEqual(run(meeting, 10)[0], 0)

    def test_works_with_invitations_switched_off(self):
        meeting = make([30], send_email_notifications=False)
        self.assertEqual(run(meeting, 30)[0], 2)

    def test_reminders_already_past_at_creation_are_not_sent(self):
        meeting = make([1440, 60], created_days_ago=0)
        meeting.created_at = START - timedelta(minutes=45)
        self.assertEqual(run(meeting, 40)[0], 0)  # 1 day and 1 hour passed before it existed
        self.assertEqual(len(meeting.reminders_sent_for), 2)

    def test_catch_up_sends_one_email_when_several_are_due(self):
        meeting = make([60, 30, 15])
        sent, _ = run(meeting, 10)
        self.assertEqual(sent, 2)
        self.assertEqual(len(meeting.reminders_sent_for), 3)

    def test_rescheduling_rearms_the_reminders(self):
        meeting = make([15])
        run(meeting, 15)
        meeting.start_at += timedelta(days=1)
        meeting.end_at += timedelta(days=1)
        notifier = Notifier()
        sent = SendMeetingParticipantRemindersUseCase(
            Repo(meeting), Notifications(), notifier
        ).execute(START + timedelta(days=1) - timedelta(minutes=15))
        self.assertEqual(sent, 2)

    def test_no_reminder_after_the_meeting_started(self):
        meeting = make([1440])
        self.assertEqual(run(meeting, -5)[0], 0)


class ReminderContentTests(TestCase):
    def _service(self, creator):
        users = SimpleNamespace(get_by_id=lambda _id: creator)
        return MeetingNotificationService(None, users, Notifier())

    def _creator(self):
        return SimpleNamespace(name="Asha", email="asha@x.com", google_email=None, is_active=True)

    def test_defaults_to_title_and_description(self):
        meeting = make([15])
        reminder = self._service(self._creator()).build_email(meeting, KIND_REMINDER)
        self.assertIsNone(reminder.subject)
        self.assertEqual(reminder.description, "Agenda")
        self.assertEqual(MeetingReminderEmailer._subject(reminder), "Demo")
        self.assertEqual(reminder.reply_to, "asha@x.com")

    def test_custom_subject_and_message_win(self):
        meeting = make([15], reminder_subject=" Pricing call tomorrow ", reminder_message="Bring the deck")
        reminder = self._service(self._creator()).build_email(meeting, KIND_REMINDER)
        self.assertEqual(MeetingReminderEmailer._subject(reminder), "Pricing call tomorrow")
        self.assertEqual(reminder.description, "Bring the deck")
