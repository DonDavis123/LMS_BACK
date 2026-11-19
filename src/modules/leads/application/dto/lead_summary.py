from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.modules.leads.domain.entities.lead_summary import LeadSummary


@dataclass(frozen=True)
class LeadSummaryResult:
    """What the summary generator hands back (no lead data, only the text)."""

    headline: str
    key_points: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    model_name: str | None = None


@dataclass(frozen=True)
class LeadSummaryResponseDTO:
    """Read model of ``GET`` / ``POST /leads/<id>/summary/``.

    The summary is written on demand (``POST``) and the latest one is stored,
    so ``generated_at`` is the moment it was written, however long ago.
    """

    lead_id: UUID
    headline: str
    key_points: list[str]
    next_steps: list[str]
    generated_at: datetime
    model_name: str | None
    # How much history the summary is based on (shown as "Based on ...").
    timeline_events_used: int
    calls_used: int

    @classmethod
    def from_entity(cls, summary: LeadSummary) -> "LeadSummaryResponseDTO":
        return cls(
            lead_id=summary.lead_id,
            headline=summary.headline,
            key_points=list(summary.key_points),
            next_steps=list(summary.next_steps),
            generated_at=summary.generated_at,
            model_name=summary.model_name,
            timeline_events_used=summary.timeline_events_used,
            calls_used=summary.calls_used,
        )
