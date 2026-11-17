from datetime import datetime, timezone
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
from src.modules.leads.application.services.lead_summary_dossier import (
    MAX_CALLS,
    MAX_TIMELINE_EVENTS,
    build_lead_dossier,
)
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class GenerateLeadSummaryUseCase:
    """Writes a short "where does this lead stand" summary from its history.

    Runs only when a user asks for it (nothing is stored). It reads the lead,
    its timeline and its calls (with the summaries of transcribed recordings),
    all scoped to the caller's company by the repositories.
    """

    def __init__(
        self,
        lead_repository: LeadRepository,
        timeline_repository: TimelineRepository,
        call_repository: CallRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        summary_generator: LeadSummaryGenerator,
    ):
        self.lead_repository = lead_repository
        self.timeline_repository = timeline_repository
        self.call_repository = call_repository
        self.transcript_repository = transcript_repository
        self.summary_generator = summary_generator

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

        result = self.summary_generator.generate(dossier)

        return LeadSummaryResponseDTO(
            lead_id=lead.id,
            headline=result.headline,
            key_points=result.key_points,
            next_steps=result.next_steps,
            generated_at=datetime.now(timezone.utc),
            model_name=result.model_name,
            timeline_events_used=len(events),
            calls_used=len(calls),
        )

    def _call_summaries(self, call_ids: list[UUID]) -> dict:
        grouped: dict = {}
        if not call_ids:
            return grouped
        for transcript in self.transcript_repository.get_completed_for_calls(call_ids):
            grouped.setdefault(transcript.call_id, []).append(transcript)
        return grouped
