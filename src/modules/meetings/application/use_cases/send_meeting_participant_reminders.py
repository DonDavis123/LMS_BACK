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

    Meant to run every minute from the notification cron. A meeting is
    reminded once per reminder time: ``participant_reminder_for`` remembers
    which time was already sent, so a rescheduled meeting is reminded again.
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

            reminder = self.notification_service.build_email(meeting, KIND_REMINDER)

            sent = 0
            for email in recipients.emails:
                try:
                    self.notifier.send(email, reminder)
                    sent += 1
                except Exception:
                    logger.exception(
                        "Meeting reminder email failed for meeting %s", meeting.id
                    )

            if recipients.emails and sent == 0:
                # Nothing got through (mail relay down?). Leave it unmarked so
                # the next cron run retries until the meeting ends.
                continue

            sent_total += sent
            self._mark_done(meeting, remind_at)

        return sent_total

    def _mark_done(self, meeting, remind_at: datetime) -> None:
        meeting.participant_reminder_for = remind_at
        self.meeting_repository.save(meeting)
