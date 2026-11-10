from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetContactsUseCase:

    def __init__(self, contact_repository: ContactRepository):
        self.contact_repository = contact_repository

    def execute(self, query: ListQuery) -> PaginatedResult[dict]:
        result = self.contact_repository.get_all_with_relations(query)

        return PaginatedResult(
            results=[
                {
                    "id": contact.id,
                    "name": contact.name,
                    "email": contact.email,
                    "phone": contact.phone,
                    "mobile": contact.mobile,
                    "account_id": contact.account_id,
                    "account_name": account_name,
                    "contact_owner_id": contact.contact_owner_id,
                    "contact_owner_name": contact_owner_name,
                    "next_task_due_date": next_task_due_date,
                    "next_task_status": next_task_status,
                    # Read by the export only: the list serializer does not
                    # send these, so the list API response is unchanged.
                    "secondary_email": contact.secondary_email,
                    "title": contact.title,
                    "department": contact.department,
                    "lead_source": contact.lead_source,
                    "date_of_birth": contact.date_of_birth,
                    "email_opt_out": contact.email_opt_out,
                    "mailing_address": contact.mailing_address,
                    "mailing_city": contact.mailing_city,
                    "mailing_state": contact.mailing_state,
                    "mailing_country": contact.mailing_country,
                    "mailing_postal_code": contact.mailing_postal_code,
                    "created_at": contact.created_at,
                    "updated_at": contact.updated_at,
                }
                for (
                    contact,
                    account_name,
                    contact_owner_name,
                    next_task_due_date,
                    next_task_status,
                ) in result.results
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )
