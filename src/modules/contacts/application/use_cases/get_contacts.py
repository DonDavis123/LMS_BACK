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
