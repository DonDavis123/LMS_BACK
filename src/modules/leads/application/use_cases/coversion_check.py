from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.dto.conversion_check import (
    ConversionCheckDTO,
)
from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)


class ConversionCheckUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
        account_repository: AccountRepository,
        contact_repository: ContactRepository,
    ):
        self.lead_repository = lead_repository
        self.account_repository = account_repository
        self.contact_repository = contact_repository

    def execute(
        self,
        lead_id: UUID,
    ) -> ConversionCheckDTO:

        lead = self.lead_repository.get_by_id(
            lead_id,
        )

        if lead is None:
            raise ValueError(
                "Lead not found."
            )

        if lead.is_deleted:
            raise ValueError(
                "Deleted lead cannot be converted."
            )

        if lead.is_converted:
            raise ValueError(
                "Lead is already converted."
            )

        account_matches = (
            self.account_repository.find_conversion_matches(
                account_name=lead.company_name,
                website=lead.website,
                phone=lead.phone,
            )
        )

        contact_matches = (
            self.contact_repository.find_conversion_matches(
                name=lead.name,
                email=lead.email,
                phone=lead.phone,
                mobile=lead.mobile_number,
            )
        )

        return ConversionCheckDTO(
            lead_id=lead.id,
            account_matches=account_matches,
            contact_matches=contact_matches,
        )