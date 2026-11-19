from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class AccountSummary:
    """The stored AI summary of one account (at most one per account).

    A refresh does not edit this record: the old summary is deleted and the
    new one takes its place (see ``AccountSummaryRepository.replace_for_account``).
    """

    id: UUID
    account_id: UUID
    headline: str
    key_points: list[str]
    next_steps: list[str]
    model_name: str | None
    # How much history the summary is based on (shown as "Based on ...").
    timeline_events_used: int
    calls_used: int
    contacts_used: int
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        *,
        account_id: UUID,
        headline: str,
        key_points: list[str],
        next_steps: list[str],
        model_name: str | None,
        timeline_events_used: int,
        calls_used: int,
        contacts_used: int,
    ) -> "AccountSummary":
        if account_id is None:
            raise ValueError("Summary account is required.")

        if not isinstance(headline, str) or not headline.strip():
            raise ValueError("Summary headline cannot be empty.")

        return cls(
            id=uuid4(),
            account_id=account_id,
            headline=headline.strip(),
            key_points=list(key_points or []),
            next_steps=list(next_steps or []),
            model_name=model_name,
            timeline_events_used=timeline_events_used,
            calls_used=calls_used,
            contacts_used=contacts_used,
            generated_at=datetime.now(timezone.utc),
        )
