from dataclasses import dataclass

from src.modules.calls.domain.entities.call import Call


@dataclass(frozen=True)
class GetCallDTO:
    """Application read model for call detail/list responses.

    The domain Call keeps only relationship IDs. This DTO adds the display
    names required by the presentation layer without polluting the domain
    entity with persistence-specific concerns.
    """

    call: Call
    lead_name: str | None
    contact_name: str | None
    account_name: str | None
    owner_name: str | None = None
