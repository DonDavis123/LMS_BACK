from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class LeadSummary:
    """The stored AI summary of one lead (at most one per lead).

    A refresh does not edit this record: the old summary is deleted and the
    new one takes its place (see ``LeadSummaryRepository.replace_for_lead``).
    """

    id: UUID
    lead_id: UUID
    headline: str
    key_points: list[str]
    next_steps: list[str]
    model_name: str | None
    # How much history the summary is based on (shown as "Based on ...").
    timeline_events_used: int
    calls_used: int
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        *,
        lead_id: UUID,
        headline: str,
        key_points: list[str],
        next_steps: list[str],
        model_name: str | None,
        timeline_events_used: int,
        calls_used: int,
    ) -> "LeadSummary":
        if lead_id is None:
            raise ValueError("Summary lead is required.")

        if not isinstance(headline, str) or not headline.strip():
            raise ValueError("Summary headline cannot be empty.")

        return cls(
            id=uuid4(),
            lead_id=lead_id,
            headline=headline.strip(),
            key_points=list(key_points or []),
            next_steps=list(next_steps or []),
            model_name=model_name,
            timeline_events_used=timeline_events_used,
            calls_used=calls_used,
            generated_at=datetime.now(timezone.utc),
        )
