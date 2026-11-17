from dataclasses import dataclass

from src.modules.deals.domain.entities.deal import Deal


@dataclass(frozen=True)
class GetDealDTO:
    """Application read model for deal detail/list responses.

    The domain Deal keeps only relationship IDs. This DTO adds the display
    names required by the presentation layer.
    """

    deal: Deal
    owner_name: str | None = None
    account_name: str | None = None
    contact_name: str | None = None
    source_lead_name: str | None = None
