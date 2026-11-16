import logging
from datetime import datetime, timedelta

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    MeetingReminder,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.services.meeting_conference_service import (
    MeetingConferenceService,
)

logger = logging.getLogger(__name__)

DEFAULT_REMINDER_LEAD = timedelta(minutes=15)


class SendMeetingParticipantRemindersUseCase:
    """Emails the Meet link to participants shortly before a meeting starts.

    Meant to run every minute from the notification cron. A meeting is
    reminded once per reminder time: ``participant_reminder_for`` remembers
    which time was already sent, so a rescheduled meeting is reminded again.
    """

    def __init__(
        self,
        meeting_repository: MeetingRepository,
        conference_service: MeetingConferenceService,
        notifier: MeetingReminderNotifier,
        default_lead: timedelta = DEFAULT_REMINDER_LEAD,
    ):
        self.meeting_repository = meeting_repository
        self.conference_service = conference_service
        self.notifier = notifier
        self.default_lead = default_lead

    def execute(self, as_of: datetime) -> int:
        """Return how many reminder emails were sent."""
        sent_total = 0

        for meeting in self.meeting_repository.get_conference_meetings_not_ended(as_of):
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

            recipients = self.conference_service.reminder_recipient_emails(meeting)
            detail = self.meeting_repository.get_by_id_with_details(meeting.id)
            reminder = MeetingReminder(
                title=meeting.title,
                start_at=meeting.start_at,
                end_at=meeting.end_at,
                meet_link=meeting.meet_link,
                host_name=detail.host_name if detail else "",
                location=meeting.location,
                description=meeting.description,
            )

            sent = 0
            for email in recipients:
                try:
                    self.notifier.send(email, reminder)
                    sent += 1
                except Exception:
                    logger.exception(
                        "Meeting reminder email failed for meeting %s", meeting.id
                    )

            if recipients and sent == 0:
                # Nothing got through (mail relay down?). Leave it unmarked so
                # the next cron run retries until the meeting ends.
                continue

            sent_total += sent
            self._mark_done(meeting, remind_at)

        return sent_total

    def _mark_done(self, meeting, remind_at: datetime) -> None:
        meeting.participant_reminder_for = remind_at
        self.meeting_repository.save(meeting)
