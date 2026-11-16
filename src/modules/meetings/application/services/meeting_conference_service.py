import logging
from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.interfaces.video_conference_provider import (
    ConferenceEvent,
    VideoConferenceError,
    VideoConferenceNotConnectedError,
    VideoConferenceProvider,
)
from src.modules.meetings.application.services.meeting_recipients import (
    MeetingRecipientResolver,
)
from src.modules.meetings.domain.entities.meeting import DEFAULT_REMINDER_LEAD, Meeting
from src.modules.users.application.interfaces.user_repository import UserRepository

logger = logging.getLogger(__name__)

# Google Calendar accepts reminder overrides up to four weeks ahead.
_MAX_REMINDER_MINUTES = 40320


class MeetingConferenceService:
    """Keeps a meeting's Google Calendar event (with or without a Meet link)
    in step with the CRM meeting.

    Use cases call this *after* their database transaction has committed, so a
    slow or failing provider can never roll back or block the CRM data.
    """

    def __init__(
        self,
        meeting_repository: MeetingRepository,
        user_repository: UserRepository,
        provider: VideoConferenceProvider,
    ):
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository
        self.provider = provider
        self.recipients = MeetingRecipientResolver(meeting_repository, user_repository)

    def ensure_can_create(
        self,
        host_id: UUID,
        is_all_day: bool,
        acting_user_id: UUID | None = None,
    ) -> None:
        """Fail fast, before anything is saved."""
        if is_all_day:
            raise ValueError("Google Meet cannot be added to all-day meetings.")

        if self.provider.get_connected_account_email(host_id) is None:
            if acting_user_id is not None and acting_user_id == host_id:
                raise VideoConferenceNotConnectedError(
                    "Connect your Google account before adding Google Meet."
                )
            raise VideoConferenceNotConnectedError(
                "The meeting host must connect their Google account before "
                "Google Meet can be added."
            )

    def can_create_calendar_event(self, meeting: Meeting) -> bool:
        """A plain calendar event needs a connected host and a timed meeting."""
        if meeting.is_all_day:
            return False
        try:
            return self.provider.get_connected_account_email(meeting.host_id) is not None
        except Exception:  # noqa: BLE001 - never block a save on a Google lookup
            logger.warning("Could not check Google connection for meeting %s", meeting.id)
            return False

    def attach(self, meeting: Meeting) -> Meeting:
        """Create the event + Meet link for a saved meeting.

        Provider failures are stored on the meeting (status ``failed``) and not
        raised, so the CRM meeting always survives.
        """
        owner_id = meeting.host_id
        try:
            event = self._build_event(meeting, owner_id, with_meet=True)
            result = self.provider.create_event(owner_id, event)
        except VideoConferenceError as exc:
            logger.warning("Google Meet creation failed for meeting %s: %s", meeting.id, exc)
            meeting.mark_conference_failed(self.provider.provider_type, str(exc))
            return self.meeting_repository.save(meeting)

        meeting.mark_conference_created(
            provider=self.provider.provider_type,
            external_event_id=result.event_id,
            meet_link=result.meet_link,
            calendar_owner_id=owner_id,
        )
        return self.meeting_repository.save(meeting)

    def attach_calendar_event(self, meeting: Meeting) -> Meeting:
        """Create a Google Calendar event *without* Meet, so invitees get a
        calendar invite. Best effort: on any failure the meeting is returned
        unchanged and the caller falls back to plain emails."""
        owner_id = meeting.host_id
        try:
            event = self._build_event(meeting, owner_id, with_meet=False)
            result = self.provider.create_event(owner_id, event)
        except VideoConferenceError as exc:
            logger.warning("Google Calendar event failed for meeting %s: %s", meeting.id, exc)
            return meeting

        meeting.mark_calendar_event_created(result.event_id, owner_id)
        return self.meeting_repository.save(meeting)

    def add_meet_to_event(self, meeting: Meeting) -> Meeting:
        """Add a Meet link to a meeting whose calendar event has none yet."""
        owner_id = meeting.calendar_owner_id or meeting.host_id
        try:
            event = self._build_event(meeting, owner_id, with_meet=True)
            link = self.provider.update_event(owner_id, meeting.external_event_id, event)
            if not link:
                raise VideoConferenceError("Google did not return a Meet link for the event.")
        except VideoConferenceError as exc:
            logger.warning("Adding Google Meet failed for meeting %s: %s", meeting.id, exc)
            meeting.mark_conference_failed(self.provider.provider_type, str(exc))
            return self.meeting_repository.save(meeting)

        meeting.mark_conference_created(
            provider=self.provider.provider_type,
            external_event_id=meeting.external_event_id,
            meet_link=link,
            calendar_owner_id=owner_id,
        )
        return self.meeting_repository.save(meeting)

    def sync(self, meeting: Meeting) -> Meeting:
        """Push title/time/participant changes to the existing event."""
        if not meeting.external_event_id:
            return meeting

        owner_id = meeting.calendar_owner_id or meeting.host_id
        previous_error = meeting.conference_error
        try:
            event = self._build_event(meeting, owner_id, with_meet=False)
            self.provider.update_event(owner_id, meeting.external_event_id, event)
            meeting.conference_error = None
        except VideoConferenceError as exc:
            # The event still exists; keep its status and surface the sync
            # problem so it can be retried.
            logger.warning("Google event sync failed for meeting %s: %s", meeting.id, exc)
            meeting.conference_error = str(exc)[:1000]

        if meeting.conference_error != previous_error:
            return self.meeting_repository.save(meeting)
        return meeting

    def cancel(self, meeting: Meeting) -> None:
        """Cancel the event (Google emails the cancellation when email
        notifications are on). Best effort."""
        if not meeting.external_event_id:
            return

        owner_id = meeting.calendar_owner_id or meeting.host_id
        try:
            self.provider.cancel_event(
                owner_id,
                meeting.external_event_id,
                notify_attendees=meeting.send_email_notifications,
            )
        except VideoConferenceError as exc:
            logger.warning("Google event cancel failed for meeting %s: %s", meeting.id, exc)

    def _build_event(self, meeting: Meeting, owner_id: UUID, with_meet: bool) -> ConferenceEvent:
        return ConferenceEvent(
            title=meeting.title,
            description=meeting.description,
            location=meeting.location,
            start_at=meeting.start_at,
            end_at=meeting.end_at,
            attendee_emails=self._attendee_emails(meeting, owner_id),
            client_event_id=meeting.id.hex,
            with_meet=with_meet,
            notify_attendees=meeting.send_email_notifications,
            reminder_minutes=(
                self._reminder_minutes(meeting) if meeting.reminder_offsets is None else None
            ),
            reminder_overrides=(
                None
                if meeting.reminder_offsets is None
                else tuple(
                    min(minutes, _MAX_REMINDER_MINUTES)
                    for minutes in meeting.reminder_offsets
                )
            ),
        )

    @staticmethod
    def _reminder_minutes(meeting: Meeting) -> int:
        remind_at = meeting.participant_reminder_time(DEFAULT_REMINDER_LEAD)
        minutes = int((meeting.start_at - remind_at).total_seconds() // 60)
        return max(0, min(minutes, _MAX_REMINDER_MINUTES))

    def _attendee_emails(self, meeting: Meeting, owner_id: UUID) -> tuple[str, ...]:
        """Everyone Google should invite: the host, participants *and* Related
        To leads/contacts, minus the organizer (who owns the event)."""
        organizer_email = (self.provider.get_connected_account_email(owner_id) or "").lower()
        resolved = self.recipients.resolve(
            meeting,
            exclude_user_ids={owner_id},
            exclude_emails={organizer_email} if organizer_email else set(),
        )
        return resolved.emails
