from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class LeadSummaryResult:
    """What the summary generator hands back (no lead data, only the text)."""

    headline: str
    key_points: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    model_name: str | None = None


@dataclass(frozen=True)
class LeadSummaryResponseDTO:
    """Read model of ``POST /leads/<id>/summary/``.

    The summary is generated on demand and never stored, so ``generated_at``
    is simply the moment of the request.
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
