from uuid import UUID

from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.leads.application.dto.lead_summary import LeadSummaryResponseDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.application.interfaces.lead_summary_generator import (
    LeadSummaryGenerator,
    LeadSummaryUnavailableError,
)
from src.modules.leads.application.interfaces.lead_summary_repository import (
    LeadSummaryRepository,
)
from src.modules.leads.application.services.lead_summary_dossier import (
    MAX_CALLS,
    MAX_TIMELINE_EVENTS,
    build_lead_dossier,
)
from src.modules.leads.domain.entities.lead_summary import LeadSummary
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class GenerateLeadSummaryUseCase:
    """Writes a short "where does this lead stand" summary from its history.

    Runs only when a user asks for it. It reads the lead, its timeline and its
    calls (with the summaries of transcribed recordings), all scoped to the
    caller's company by the repositories.

    The result is stored as the lead's current summary. A refresh deletes the
    previous summary permanently and stores the new one in its place; when
    the model fails nothing is touched and the previous summary stays.
    """

    def __init__(
        self,
        lead_repository: LeadRepository,
        timeline_repository: TimelineRepository,
        call_repository: CallRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        summary_generator: LeadSummaryGenerator,
        summary_repository: LeadSummaryRepository | None = None,
    ):
        self.lead_repository = lead_repository
        self.timeline_repository = timeline_repository
        self.call_repository = call_repository
        self.transcript_repository = transcript_repository
        self.summary_generator = summary_generator
        # ``None`` keeps the old behaviour: generate without storing.
        self.summary_repository = summary_repository

    def execute(self, lead_id: UUID) -> LeadSummaryResponseDTO:
        # Check the setup first: no point reading the history without a model.
        if not self.summary_generator.is_configured():
            raise LeadSummaryUnavailableError("Lead summaries are not configured.")

        found = self.lead_repository.get_by_id_with_owner(lead_id)
        if found is None:
            raise ValueError("Lead not found.")
        lead, owner_name = found

        events = self.timeline_repository.get_for_entity("LEAD", lead.id)[:MAX_TIMELINE_EVENTS]
        calls = self.call_repository.get_by_related_record(
            lead_id=lead.id,
            limit=MAX_CALLS,
        )
        call_summaries = self._call_summaries([item.call.id for item in calls])

        dossier = build_lead_dossier(
            lead=lead,
            owner_name=owner_name,
            events=events,
            calls=calls,
            call_summaries=call_summaries,
        )

        # Raises LeadSummaryError on failure, before anything is deleted.
        result = self.summary_generator.generate(dossier)

        summary = LeadSummary.create(
            lead_id=lead.id,
            headline=result.headline,
            key_points=result.key_points,
            next_steps=result.next_steps,
            model_name=result.model_name,
            timeline_events_used=len(events),
            calls_used=len(calls),
        )

        if self.summary_repository is not None:
            # Old summary deleted + new one stored, in one transaction.
            summary = self.summary_repository.replace_for_lead(summary)

        return LeadSummaryResponseDTO.from_entity(summary)

    def _call_summaries(self, call_ids: list[UUID]) -> dict:
        grouped: dict = {}
        if not call_ids:
            return grouped
        for transcript in self.transcript_repository.get_completed_for_calls(call_ids):
            grouped.setdefault(transcript.call_id, []).append(transcript)
        return grouped
