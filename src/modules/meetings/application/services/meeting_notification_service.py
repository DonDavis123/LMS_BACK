import logging
from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_reminder_notifier import (
    KIND_CANCELLATION,
    KIND_INVITATION,
    KIND_REMINDER,
    KIND_UPDATE,
    MeetingReminder,
    MeetingReminderNotifier,
)
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.services.meeting_conference_service import (
    MeetingConferenceService,
)
from src.modules.meetings.application.services.meeting_recipients import (
    MeetingRecipientResolver,
    MeetingRecipients,
)
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus
from src.modules.users.application.interfaces.user_repository import UserRepository

logger = logging.getLogger(__name__)


class MeetingNotificationService:
    """Emails everyone a meeting concerns, whether or not it has Google Meet.

    * Meeting has a Google Calendar event -> Google sends the invite, updates
      and cancellation (the event lists the host, participants and Related To
      records as attendees).
    * No event (host not connected to Google, all-day meeting, Google
      failure) -> this service emails the invite, updates and cancellation
      itself with the same mail setup as the reminder.
    * The reminder before the meeting is always sent by this service.

    Use cases call it *after* their transaction commits; it never raises, so a
    mail problem cannot undo the meeting.
    """

    def __init__(
        self,
        meeting_repository: MeetingRepository,
        user_repository: UserRepository,
        notifier: MeetingReminderNotifier,
        conference_service: MeetingConferenceService | None = None,
    ):
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository
        self.notifier = notifier
        self.conference_service = conference_service
        self.recipients = MeetingRecipientResolver(meeting_repository, user_repository)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def on_created(self, meeting: Meeting, acting_user_id: UUID | None = None) -> Meeting:
        """Invite everyone for a newly scheduled meeting."""
        if not meeting.send_email_notifications:
            return meeting

        acting = {acting_user_id} if acting_user_id else set()

        if not meeting.external_event_id and self.conference_service is not None:
            if self.conference_service.can_create_calendar_event(meeting):
                meeting = self.conference_service.attach_calendar_event(meeting)

        if meeting.external_event_id:
            # Google emails the invite; only report who it cannot reach.
            resolved = self.recipients.resolve(meeting, exclude_user_ids={meeting.host_id})
            meeting.email_skipped = [item.to_dict() for item in resolved.skipped]
            return meeting

        self._email(meeting, KIND_INVITATION, exclude_user_ids=acting)
        return meeting

    def recipient_snapshot(
        self, meeting: Meeting, acting_user_id: UUID | None = None
    ) -> frozenset[str]:
        """Lower-cased addresses that currently hear about the meeting."""
        acting = {acting_user_id} if acting_user_id else set()
        resolved = self.recipients.resolve(meeting, exclude_user_ids=acting)
        return frozenset(email.lower() for email in resolved.emails)

    def on_updated(
        self,
        meeting: Meeting,
        *,
        acting_user_id: UUID | None,
        was_notifying: bool,
        event_changed: bool,
        previous_recipients: frozenset[str],
    ) -> Meeting:
        """Tell everyone what changed (details, time, host or the guest list)."""
        if not meeting.send_email_notifications:
            return meeting

        if not was_notifying:
            # Email was just switched on: nobody has been told about it yet.
            return self.on_created(meeting, acting_user_id)

        acting = {acting_user_id} if acting_user_id else set()

        if meeting.external_event_id:
            resolved = self.recipients.resolve(meeting, exclude_user_ids={meeting.host_id})
            meeting.email_skipped = [item.to_dict() for item in resolved.skipped]
            return meeting

        resolved = self.recipients.resolve(meeting, exclude_user_ids=acting)
        meeting.email_skipped = [item.to_dict() for item in resolved.skipped]

        newcomers = [e for e in resolved.emails if e.lower() not in previous_recipients]
        existing = [e for e in resolved.emails if e.lower() in previous_recipients]
        self._send_many(meeting, KIND_INVITATION, newcomers)
        if event_changed:
            self._send_many(meeting, KIND_UPDATE, existing)
        return meeting

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def prepare_cancellation(
        self, meeting: Meeting, acting_user_id: UUID | None = None
    ) -> tuple[str, ...] | None:
        """Call *before* the meeting is deleted (the lookup needs it active).

        Returns the addresses to email, or ``None`` when Google (or nobody)
        handles the cancellation.
        """
        if not meeting.send_email_notifications or meeting.external_event_id:
            return None
        acting = {acting_user_id} if acting_user_id else set()
        return self.recipients.resolve(meeting, exclude_user_ids=acting).emails

    def send_cancellation(self, meeting: Meeting, emails: tuple[str, ...] | None) -> None:
        if emails:
            self._send_many(meeting, KIND_CANCELLATION, list(emails))

    # ------------------------------------------------------------------
    # Reminder (before the meeting starts)
    # ------------------------------------------------------------------

    def reminder_recipients(self, meeting: Meeting) -> MeetingRecipients:
        """Everyone gets the reminder email. The calendar owner is left out
        when a Google event exists, because Google already reminds them (we
        set popup + email reminders on the event)."""
        exclude: set[UUID] = set()
        if meeting.external_event_id:
            exclude.add(meeting.calendar_owner_id or meeting.host_id)
        return self.recipients.resolve(meeting, exclude_user_ids=exclude)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def build_email(self, meeting: Meeting, kind: str) -> MeetingReminder:
        host = self.user_repository.get_by_id(meeting.host_id)
        creator = (
            self.user_repository.get_by_id(meeting.created_by_id)
            if kind == KIND_REMINDER
            else None
        )
        has_meet = (
            meeting.conference_status == ConferenceStatus.CREATED and bool(meeting.meet_link)
        )
        return MeetingReminder(
            title=meeting.title,
            start_at=meeting.start_at,
            end_at=meeting.end_at,
            host_name=host.name if host is not None else "",
            meet_link=meeting.meet_link if has_meet else None,
            location=meeting.location,
            # Reminder: the creator's own text wins, otherwise the meeting
            # heading is the subject and its description is the body.
            description=(
                (meeting.reminder_message or meeting.description)
                if kind == KIND_REMINDER
                else meeting.description
            ),
            kind=kind,
            is_all_day=meeting.is_all_day,
            subject=meeting.reminder_subject if kind == KIND_REMINDER else None,
            sender_name=creator.name if creator is not None else None,
            reply_to=(
                (creator.google_email or creator.email) if creator is not None else None
            ),
        )

    def _email(self, meeting: Meeting, kind: str, exclude_user_ids: set[UUID]) -> None:
        resolved = self.recipients.resolve(meeting, exclude_user_ids=exclude_user_ids)
        meeting.email_skipped = [item.to_dict() for item in resolved.skipped]
        self._send_many(meeting, kind, list(resolved.emails))

    def _send_many(self, meeting: Meeting, kind: str, emails: list[str]) -> int:
        if not emails:
            return 0
        email = self.build_email(meeting, kind)
        sent = 0
        for address in emails:
            try:
                self.notifier.send(address, email)
                sent += 1
            except Exception:  # noqa: BLE001 - mail problems must not undo the meeting
                logger.exception(
                    "Meeting %s email failed for meeting %s", kind, meeting.id
                )
        return sent


__all__ = ["MeetingNotificationService", "KIND_REMINDER"]
