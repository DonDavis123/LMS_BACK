import logging
import re
from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.interfaces.video_conference_provider import (
    ConferenceEvent,
    VideoConferenceError,
    VideoConferenceNotConnectedError,
    VideoConferenceProvider,
)
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.users.application.interfaces.user_repository import UserRepository

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MeetingConferenceService:
    """Keeps a meeting's video-call event in step with the CRM meeting.

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

    def attach(self, meeting: Meeting) -> Meeting:
        """Create the event + Meet link for a saved meeting.

        Provider failures are stored on the meeting (status ``failed``) and not
        raised, so the CRM meeting always survives.
        """
        owner_id = meeting.host_id
        try:
            event = self._build_event(meeting, owner_id)
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

    def sync(self, meeting: Meeting) -> Meeting:
        """Push title/time/participant changes to the existing event."""
        if not meeting.external_event_id:
            return meeting

        owner_id = meeting.calendar_owner_id or meeting.host_id
        previous_error = meeting.conference_error
        try:
            event = self._build_event(meeting, owner_id)
            self.provider.update_event(owner_id, meeting.external_event_id, event)
            meeting.conference_error = None
        except VideoConferenceError as exc:
            # The link still works; keep status ``created`` and surface the
            # sync problem so it can be retried.
            logger.warning("Google event sync failed for meeting %s: %s", meeting.id, exc)
            meeting.conference_error = str(exc)[:1000]

        if meeting.conference_error != previous_error:
            return self.meeting_repository.save(meeting)
        return meeting

    def cancel(self, meeting: Meeting) -> None:
        """Cancel the event (the provider emails cancellations). Best effort."""
        if not meeting.external_event_id:
            return

        owner_id = meeting.calendar_owner_id or meeting.host_id
        try:
            self.provider.cancel_event(owner_id, meeting.external_event_id)
        except VideoConferenceError as exc:
            logger.warning("Google event cancel failed for meeting %s: %s", meeting.id, exc)

    def _build_event(self, meeting: Meeting, owner_id: UUID) -> ConferenceEvent:
        return ConferenceEvent(
            title=meeting.title,
            description=meeting.description,
            location=meeting.location,
            start_at=meeting.start_at,
            end_at=meeting.end_at,
            attendee_emails=self._attendee_emails(meeting, owner_id),
            client_event_id=meeting.id.hex,
        )

    def _attendee_emails(self, meeting: Meeting, owner_id: UUID) -> tuple[str, ...]:
        """Participants (users, leads, contacts) and the host, minus the organizer.

        "Related To" records are not invited, only participants.
        """
        candidates: list[str | None] = []

        if meeting.host_id != owner_id:
            host = self.user_repository.get_by_id(meeting.host_id)
            if host is not None and host.is_active:
                candidates.append(host.google_email or host.email)

        detail = self.meeting_repository.get_by_id_with_details(meeting.id)
        if detail is not None:
            for participant in detail.participants:
                if participant.id == owner_id:
                    continue
                candidates.append(participant.email)

        organizer_email = (self.provider.get_connected_account_email(owner_id) or "").lower()
        owner = self.user_repository.get_by_id(owner_id)
        excluded = {organizer_email}
        if owner is not None:
            excluded.add((owner.email or "").lower())
            excluded.add((owner.google_email or "").lower())
        excluded.discard("")

        seen: set[str] = set()
        emails: list[str] = []
        for candidate in candidates:
            email = (candidate or "").strip()
            key = email.lower()
            if not email or not _EMAIL_PATTERN.match(email):
                continue
            if key in excluded or key in seen:
                continue
            seen.add(key)
            emails.append(email)
        return tuple(emails)
