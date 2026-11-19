from uuid import UUID

from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.contacts.application.dto.contact_summary import ContactSummaryResponseDTO
from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.contacts.application.interfaces.contact_summary_generator import (
    ContactSummaryGenerator,
    ContactSummaryUnavailableError,
)
from src.modules.contacts.application.interfaces.contact_summary_repository import (
    ContactSummaryRepository,
)
from src.modules.contacts.application.services.contact_summary_dossier import (
    MAX_CALLS,
    MAX_TIMELINE_EVENTS,
    build_contact_dossier,
)
from src.modules.contacts.domain.entities.contact_summary import ContactSummary
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class GenerateContactSummaryUseCase:
    """Writes a short "where does this contact stand" summary from its history.

    Runs only when a user asks for it. It reads the contact, its timeline and
    its calls (with the summaries of transcribed recordings), all scoped to the
    caller's company by the repositories.

    The result is stored as the contact's current summary. A refresh deletes
    the previous summary permanently and stores the new one in its place; when
    the model fails nothing is touched and the previous summary stays.
    """

    def __init__(
        self,
        contact_repository: ContactRepository,
        timeline_repository: TimelineRepository,
        call_repository: CallRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        summary_generator: ContactSummaryGenerator,
        summary_repository: ContactSummaryRepository | None = None,
    ):
        self.contact_repository = contact_repository
        self.timeline_repository = timeline_repository
        self.call_repository = call_repository
        self.transcript_repository = transcript_repository
        self.summary_generator = summary_generator
        # ``None`` keeps the old behaviour: generate without storing.
        self.summary_repository = summary_repository

    def execute(self, contact_id: UUID) -> ContactSummaryResponseDTO:
        # Check the setup first: no point reading the history without a model.
        if not self.summary_generator.is_configured():
            raise ContactSummaryUnavailableError("Contact summaries are not configured.")

        found = self.contact_repository.get_by_id_with_relations(contact_id)
        if found is None:
            raise ValueError("Contact not found.")
        contact, account_name, owner_name = found

        events = self.timeline_repository.get_for_entity("CONTACT", contact.id)[:MAX_TIMELINE_EVENTS]
        calls = self.call_repository.get_by_related_record(
            contact_id=contact.id,
            limit=MAX_CALLS,
        )
        call_summaries = self._call_summaries([item.call.id for item in calls])

        dossier = build_contact_dossier(
            contact=contact,
            account_name=account_name,
            owner_name=owner_name,
            events=events,
            calls=calls,
            call_summaries=call_summaries,
        )

        # Raises ContactSummaryError on failure, before anything is deleted.
        result = self.summary_generator.generate(dossier)

        summary = ContactSummary.create(
            contact_id=contact.id,
            headline=result.headline,
            key_points=result.key_points,
            next_steps=result.next_steps,
            model_name=result.model_name,
            timeline_events_used=len(events),
            calls_used=len(calls),
        )

        if self.summary_repository is not None:
            # Old summary deleted + new one stored, in one transaction.
            summary = self.summary_repository.replace_for_contact(summary)

        return ContactSummaryResponseDTO.from_entity(summary)

    def _call_summaries(self, call_ids: list[UUID]) -> dict:
        grouped: dict = {}
        if not call_ids:
            return grouped
        for transcript in self.transcript_repository.get_completed_for_calls(call_ids):
            grouped.setdefault(transcript.call_id, []).append(transcript)
        return grouped
