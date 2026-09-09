from uuid import UUID

from src.modules.contacts.application.dto.get_contact_details import (
    GetContactDetailsDTO,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)


class GetContactDetailsUseCase:

    def __init__(
        self,
        contact_repository: ContactRepository,
    ):
        self.contact_repository = contact_repository

    def execute(
        self,
        contact_id: UUID,
    ) -> GetContactDetailsDTO | None:

        result = self.contact_repository.get_by_id_with_relations(
            contact_id
        )

        if result is None:
            return None

        contact, account_name, contact_owner_name = result

        return GetContactDetailsDTO(
            id=contact.id,

            name=contact.name,
            email=contact.email,
            secondary_email=contact.secondary_email,
            phone=contact.phone,
            other_phone=contact.other_phone,
            mobile=contact.mobile,
            home_phone=contact.home_phone,
            assistant_phone=contact.assistant_phone,

            title=contact.title,
            department=contact.department,
            lead_source=contact.lead_source,
            vendor_name=contact.vendor_name,

            date_of_birth=contact.date_of_birth,
            assistant=contact.assistant,
            email_opt_out=contact.email_opt_out,

            reporting_to_id=contact.reporting_to_id,

            mailing_address=contact.mailing_address,
            mailing_city=contact.mailing_city,
            mailing_state=contact.mailing_state,
            mailing_country=contact.mailing_country,
            mailing_postal_code=contact.mailing_postal_code,
            other_address=contact.other_address,

            description=contact.description,

            account_id=contact.account_id,
            account_name=account_name,

            contact_owner_id=contact.contact_owner_id,
            contact_owner_name=contact_owner_name,

            created_by_id=contact.created_by_id,
            created_at=contact.created_at,

            modified_by_id=contact.modified_by_id,
            updated_at=contact.updated_at,
        )