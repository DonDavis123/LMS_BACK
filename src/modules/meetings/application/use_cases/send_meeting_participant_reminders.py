import logging
from datetime import datetime, timedelta

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    KIND_REMINDER,
    MeetingReminder,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.entities.meeting import DEFAULT_REMINDER_LEAD

logger = logging.getLogger(__name__)

__all__ = ["SendMeetingParticipantRemindersUseCase", "DEFAULT_REMINDER_LEAD"]


class SendMeetingParticipantRemindersUseCase:
    """Emails everyone shortly before a meeting starts.

    Covers every meeting that has email notifications on, with or without a
    Google Meet link. The email carries the meeting heading and description,
    plus the Meet link when there is one. Recipients are the host, the
    participants and the Related To leads/contacts.

    Meant to run every minute from the notification cron. Each reminder the
    creator picked (1 day / 1 hour / 30 minutes / 15 minutes before) is sent
    once: ``reminders_sent_for`` remembers which times were already sent, so a
    rescheduled meeting is reminded again. Older meetings with no choice keep
    the single reminder (``reminder_at`` or 15 minutes before).
    """

    def __init__(
        self,
        meeting_repository: MeetingRepository,
        notification_service,
        notifier: MeetingReminderNotifier,
        default_lead: timedelta = DEFAULT_REMINDER_LEAD,
    ):
        self.meeting_repository = meeting_repository
        self.notification_service = notification_service
        self.notifier = notifier
        self.default_lead = default_lead

    def execute(self, as_of: datetime) -> int:
        """Return how many reminder emails were sent."""
        sent_total = 0

        for meeting in self.meeting_repository.get_email_reminder_candidates(as_of):
            if meeting.reminder_offsets is not None:
                sent_total += self._send_selected_reminders(meeting, as_of)
                continue

            remind_at = meeting.participant_reminder_time(self.default_lead)

            if remind_at > as_of:
                continue  # not due yet
            if meeting.participant_reminder_for == remind_at:
                continue  # already sent for this time

            if remind_at <= meeting.created_at:
                # Created inside the reminder window: the invite itself was
                # just sent, so a reminder now would be noise.
                self._mark_done(meeting, remind_at)
                continue

            recipients = self.notification_service.reminder_recipients(meeting)
            if recipients.skipped:
                logger.info(
                    "Meeting %s reminder: %d recipient(s) without a usable email",
                    meeting.id,
                    len(recipients.skipped),
                )

            sent = self._deliver(meeting, recipients)

            if recipients.emails and sent == 0:
                # Nothing got through (mail relay down?). Leave it unmarked so
                # the next cron run retries until the meeting ends.
                continue

            sent_total += sent
            self._mark_done(meeting, remind_at)

        return sent_total

    def _send_selected_reminders(self, meeting, as_of: datetime) -> int:
        """Reminders chosen on the meeting form, one email per chosen time."""
        times = meeting.reminder_times(self.default_lead)
        already = set(meeting.reminders_sent_for or [])

        due = [t for t in times if t <= as_of and t.isoformat() not in already]
        if not due:
            return 0

        # Times that passed before the meeting existed, or after it started
        # (cron was down), would only be noise: mark them without emailing.
        sendable = [t for t in due if t > meeting.created_at and as_of <= meeting.start_at]
        # If several came due at once, one email is enough: the closest one.
        to_send = sendable[-1:] if sendable else []

        sent = 0
        if to_send:
            recipients = self.notification_service.reminder_recipients(meeting)
            if recipients.skipped:
                logger.info(
                    "Meeting %s reminder: %d recipient(s) without a usable email",
                    meeting.id,
                    len(recipients.skipped),
                )
            sent = self._deliver(meeting, recipients)
            if recipients.emails and sent == 0:
                # Nothing got through (mail relay down?). Leave it unmarked so
                # the next cron run retries until the meeting starts.
                return 0

        # Forget times that no longer apply (meeting moved, options changed).
        meeting.reminders_sent_for = [
            t.isoformat() for t in times if t.isoformat() in already or t in due
        ]
        self.meeting_repository.save(meeting)
        return sent

    def _deliver(self, meeting, recipients) -> int:
        reminder = self.notification_service.build_email(meeting, KIND_REMINDER)
        sent = 0
        for email in recipients.emails:
            try:
                self.notifier.send(email, reminder)
                sent += 1
            except Exception:
                logger.exception("Meeting reminder email failed for meeting %s", meeting.id)
        return sent

    def _mark_done(self, meeting, remind_at: datetime) -> None:
        meeting.participant_reminder_for = remind_at
        self.meeting_repository.save(meeting)
